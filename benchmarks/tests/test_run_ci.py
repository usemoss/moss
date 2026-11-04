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

run_ci = importlib.import_module("run_ci")
BenchmarkResult = importlib.import_module("stats").BenchmarkResult
TEST_CREDENTIALS = {"MOSS_PROJECT_ID": "fake-project-id", "MOSS_PROJECT_KEY": "fake-project-key"}


def completed_run():
    raw = [float(index % 10 + 1) for index in range(750)]
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
    def invoke(self, *, result=None, error=None, credentials=TEST_CREDENTIALS, args=()):
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
                code = run_ci.main(["--output", str(path), *args])
            text = path.read_text()
            return code, json.loads(text), text, stderr.getvalue(), call

    def test_success_records_raw_metrics_without_claiming_quality_or_guards(self):
        code, record, _, _, call = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "success")
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["measured_query_count"], 750)
        self.assertEqual(len(record["raw_latencies_ms"]), 750)
        self.assertEqual([record["latency_ms"][name] for name in ("p50", "p95", "p99")], [5.0, 10.0, 10.0])
        self.assertEqual(record["configuration"]["actual_doc_count"], 100000)
        self.assertEqual(record["quality"], {"status": "not_configured", "recall": None})
        self.assertEqual(record["regression"]["status"], "not_configured")
        self.assertEqual(record["provenance"]["runtime_under_test"], "installed-release")
        call.assert_awaited_once_with("fake-project-id", "fake-project-key")

    def test_measurement_error_redacts_overlapping_credentials_before_json_encoding(self):
        credentials = {
            "MOSS_PROJECT_ID": "example-id",
            "MOSS_PROJECT_KEY": 'prefix-example-id-"-with-newline\n-private-suffix',
        }
        message = " / ".join(credentials.values())
        code, record, text, stderr, _ = self.invoke(
            error=RuntimeError(message), credentials=credentials,
        )
        self.assertEqual((code, record["status"]), (1, "failed"))
        self.assertEqual(record["error"], {"type": "RuntimeError", "message": "[redacted] / [redacted]"})
        self.assertIn("[redacted] / [redacted]", stderr)
        self.assertNotRegex(text + stderr, "example-id|private-suffix")
        self.assertIn("completed_at_utc", record)

    def test_invalid_measurements_fail_with_valid_json(self):
        for field, value, message in (
            ("latencies_ms", [1.0] * 749, "Expected 750"),
            ("latencies_ms", [float("nan")] * 750, "Measured durations"),
            ("first_query_ms", float("inf"), "First-query duration"),
        ):
            with self.subTest(message=message):
                result = completed_run()
                setattr(result.measurement, field, value)
                code, record, text, _, _ = self.invoke(result=result)
                self.assertEqual((code, record["status"]), (1, "failed"))
                self.assertIn(message, record["error"]["message"])
                self.assertNotRegex(text, "NaN|Infinity")

    def test_explicit_env_file_is_supported_and_credentials_are_not_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "credentials.env"
            env_file.write_text("MOSS_PROJECT_ID=file-id\nMOSS_PROJECT_KEY=file-key\n")
            code, _, text, _, call = self.invoke(credentials={}, args=("--env-file", str(env_file)))
            self.assertEqual(code, 0)
            call.assert_awaited_once_with("file-id", "file-key")
            self.assertNotIn("file-key", text)

    def test_missing_credentials_fails_in_subprocess_without_implicit_dotenv(self):
        # Forbid discovery before imports, so a regression cannot read the
        # developer's actual ignored .env or accidentally start a live run.
        script = """
from pathlib import Path
import runpy
import sys
import dotenv

def forbidden(*args, **kwargs):
    raise AssertionError('Implicit dotenv discovery is forbidden')

dotenv.load_dotenv = dotenv.dotenv_values = forbidden
entrypoint = Path(sys.argv.pop(1))
sys.path.insert(0, str(entrypoint.parent))
runpy.run_path(str(entrypoint), run_name='__main__')
"""
        environment = {key: value for key, value in os.environ.items() if key not in TEST_CREDENTIALS}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            process = subprocess.run(
                [sys.executable, "-c", script, str(BENCHMARKS / "run_ci.py"), "--output", str(output)],
                cwd=directory, env=environment, text=True, capture_output=True,
                timeout=30,
            )
            self.assertEqual(process.returncode, 1, process.stderr)
            self.assertNotIn("Implicit dotenv discovery", process.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertIn("Set MOSS_PROJECT_ID", record["error"]["message"])
            self.assertEqual(record["provenance"]["runtime_under_test"], "installed-release")


if __name__ == "__main__":
    unittest.main()
