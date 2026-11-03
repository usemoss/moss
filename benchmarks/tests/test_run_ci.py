"""Offline checks for the real CI entry point and its result/exit contract."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


BENCHMARKS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARKS))

bench_moss = importlib.import_module("bench_moss")
run_ci = importlib.import_module("run_ci")
BenchmarkResult = importlib.import_module("stats").BenchmarkResult


def completed_run():
    count = bench_moss.QUERY_ROUNDS * len(run_ci.get_queries())
    raw = [float(index % 10 + 1) for index in range(count)]
    return SimpleNamespace(
        measurement=SimpleNamespace(
            result=BenchmarkResult("controlled measurement", raw),
            latencies_ms=raw,
            first_query_ms=99.0,
            rankings={"query": ["doc_0", "doc_1", "doc_2", "doc_3", "doc_4"]},
        ),
        configuration={"mode": "local-session", "actual_doc_count": 100000},
        setup={"build_seconds": 2.0},
    )


class ResultContractTests(unittest.TestCase):
    def invoke(self, *, result=None, error=None, credentials=None):
        credentials = credentials or {
            "MOSS_PROJECT_ID": "fake-project-id",
            "MOSS_PROJECT_KEY": "fake-project-key",
        }
        call = AsyncMock(return_value=result or completed_run(), side_effect=error)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with (
                patch.dict(os.environ, credentials, clear=True),
                patch.object(run_ci, "provenance", return_value={"runtime_under_test": "installed-release"}),
                patch.object(run_ci, "run_local_async", call),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
            ):
                code = run_ci.main(["--output", str(path)])
            text = path.read_text()
            return code, json.loads(text), text, stderr.getvalue(), call

    def test_success_records_raw_metrics_without_claiming_quality_or_guards(self):
        code, record, _, _, call = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["measured_query_count"], 750)
        self.assertEqual(len(record["raw_latencies_ms"]), 750)
        self.assertEqual(record["latency_ms"]["p50"], 5.0)
        self.assertEqual(record["latency_ms"]["p95"], 10.0)
        self.assertEqual(record["configuration"]["actual_doc_count"], 100000)
        self.assertEqual(record["quality"], {"status": "not_configured", "recall": None})
        self.assertEqual(record["regression"]["status"], "not_configured")
        self.assertEqual(record["provenance"]["runtime_under_test"], "installed-release")
        call.assert_awaited_once_with("fake-project-id", "fake-project-key")

    def test_measurement_error_is_nonzero_and_leaves_sanitized_failure_json(self):
        credentials = {
            "MOSS_PROJECT_ID": "example-id",
            "MOSS_PROJECT_KEY": 'example-key-"-with-newline\n-end',
        }
        message = f"service rejected {credentials['MOSS_PROJECT_ID']} / {credentials['MOSS_PROJECT_KEY']}"
        code, record, _, stderr, _ = self.invoke(
            error=RuntimeError(message), credentials=credentials,
        )
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["error"]["type"], "RuntimeError")
        for secret in credentials.values():
            self.assertNotIn(secret, record["error"]["message"])
            self.assertNotIn(secret, stderr)
        self.assertIn("[redacted]", record["error"]["message"])
        self.assertIn("completed_at_utc", record)

    def test_incomplete_measurements_cannot_be_reported_as_success(self):
        result = completed_run()
        result.measurement.latencies_ms.pop()
        code, record, _, _, _ = self.invoke(result=result)
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")
        self.assertIn("Expected 750", record["error"]["message"])

    def test_overlapping_credentials_are_redacted_as_whole_values(self):
        credentials = {
            "MOSS_PROJECT_ID": "example-id",
            "MOSS_PROJECT_KEY": "prefix-example-id-private-suffix",
        }
        code, record, text, stderr, _ = self.invoke(
            error=RuntimeError("example-id / prefix-example-id-private-suffix"),
            credentials=credentials,
        )
        self.assertEqual(code, 1)
        self.assertEqual(record["error"]["message"], "[redacted] / [redacted]")
        self.assertNotIn("private-suffix", text)
        self.assertNotIn("private-suffix", stderr)

    def test_nonfinite_samples_fail_without_writing_invalid_json(self):
        result = completed_run()
        result.measurement.latencies_ms[0] = float("nan")
        code, record, text, _, _ = self.invoke(result=result)
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("NaN", text)

    def test_invalid_first_query_fails_with_parseable_failure_json(self):
        result = completed_run()
        result.measurement.first_query_ms = float("inf")
        code, record, text, _, _ = self.invoke(result=result)
        self.assertEqual(code, 1)
        self.assertEqual(record["status"], "failed")
        self.assertNotIn("Infinity", text)

    def test_explicit_env_file_is_supported_and_credentials_are_not_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "credentials.env"
            env_file.write_text("MOSS_PROJECT_ID=file-id\nMOSS_PROJECT_KEY=file-key\n")
            output = Path(directory) / "result.json"
            call = AsyncMock(return_value=completed_run())
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(run_ci, "provenance", return_value={}),
                patch.object(run_ci, "run_local_async", call),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(run_ci.main([
                    "--env-file", str(env_file), "--output", str(output),
                ]), 0)
            call.assert_awaited_once_with("file-id", "file-key")
            self.assertNotIn("file-key", output.read_text())


class CommandLineTests(unittest.TestCase):
    def test_missing_credentials_fails_in_subprocess_without_implicit_dotenv(self):
        # Forbid discovery before imports, so a regression cannot read the
        # developer's actual ignored .env or accidentally start a live run.
        script = """
import dotenv
import runpy
import sys
def forbidden(*args, **kwargs):
    raise AssertionError('Implicit dotenv discovery is forbidden')
dotenv.load_dotenv = forbidden
sys.path.insert(0, sys.argv[1])
sys.argv = [sys.argv[1] + '/run_ci.py', '--output', sys.argv[2]]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
        environment = dict(os.environ)
        for name in ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY"):
            environment.pop(name, None)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            process = subprocess.run(
                [sys.executable, "-c", script, str(BENCHMARKS), str(output)],
                cwd=directory, env=environment, text=True, capture_output=True,
                timeout=30,
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertIn("Set MOSS_PROJECT_ID", record["error"]["message"])
            self.assertNotIn("Implicit dotenv discovery", process.stderr)
            self.assertEqual(record["provenance"]["runtime_under_test"], "installed-release")


if __name__ == "__main__":
    unittest.main()
