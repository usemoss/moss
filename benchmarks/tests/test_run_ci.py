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
make_reference = importlib.import_module("competitor_agreement").make_reference
TEST_CREDENTIALS = {"MOSS_PROJECT_ID": "fake-project-id", "MOSS_PROJECT_KEY": "fake-project-key"}
TEST_PROVENANCE = {
    "runtime_under_test": "installed-release",
    "python": "3.12.8",
    "system": "Linux",
    "machine": "x86_64",
    "cpu_count": 4,
    "runner_label": "ubuntu-24.04",
}
WORKLOAD = {
    "mode": "local-session",
    "setup_mode": "fresh-build",
    "dataset_sha256": "d" * 64,
    "query_sha256": "e" * 64,
    "model_id": "moss-minilm",
    "model_artifact_id": None,
    "doc_count": 100000,
    "query_count": 15,
    "top_k": 5,
    "alpha": 1,
    "warmup_rounds": 3,
    "query_rounds": 50,
}
LATENCY_CONTEXT = {
    "workload": WORKLOAD,
    "runner": {"label": "ubuntu-24.04", "os": "Linux", "machine": "x86_64", "cpu_count": 4, "python": "3.12"},
}


def completed_run(latency_scale=1.0):
    raw = [(index % 10 + 1) * latency_scale for index in range(750)]
    return SimpleNamespace(
        measurement=SimpleNamespace(
            result=BenchmarkResult("controlled measurement", raw),
            latencies_ms=raw,
            first_query_ms=99.0,
            rankings={"query": ["doc_0", "doc_1", "doc_2", "doc_3", "doc_4"]},
        ),
        configuration={**WORKLOAD, "actual_doc_count": 100000},
        setup={"build_seconds": 2.0},
    )


def baseline_json(**overrides):
    return json.dumps({
        "baseline_commit": "a" * 40,
        "p95_ms": 8.0,
        "max_slowdown_pct": 25.0,
        "compatibility": LATENCY_CONTEXT,
        **overrides,
    })


class ResultContractTests(unittest.TestCase):
    def invoke(self, *, result=None, error=None, credentials=TEST_CREDENTIALS, args=()):
        call = AsyncMock(return_value=result or completed_run(), side_effect=error)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            with (
                patch.dict(os.environ, credentials, clear=True),
                patch.object(run_ci, "provenance", return_value=TEST_PROVENANCE),
                patch.object(run_ci, "run_local_async", call),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
            ):
                code = run_ci.main(["--output", str(path), *args])
            text = path.read_text()
            return code, json.loads(text), text, stderr.getvalue(), call

    def invoke_with_baseline(self, contents, *, result=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            if contents is not None:
                path.write_text(contents)
            return self.invoke(result=result, args=("--baseline", str(path)))

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
        self.assertEqual(record["latency_context"], LATENCY_CONTEXT)
        self.assertEqual(record["provenance"]["runtime_under_test"], "installed-release")
        call.assert_awaited_once_with("fake-project-id", "fake-project-key")

    def test_output_cannot_replace_credentials_or_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / "credentials.env"
            corpus = Path(directory) / "corpus.json"
            credentials.write_text("SENTINEL=keep\n", encoding="utf-8")
            corpus.write_text("[]", encoding="utf-8")
            for path, args in ((credentials, ["--env-file", str(credentials)]), (corpus, [])):
                with (
                    self.subTest(path=path.name),
                    patch.object(run_ci, "FIXED_CORPUS_PATH", corpus),
                    patch.dict(os.environ, {}, clear=True),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    original = path.read_bytes()
                    with self.assertRaises(SystemExit) as stopped:
                        run_ci.main(["--output", str(path), *args])
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertEqual(path.read_bytes(), original)

    def test_latency_guard_allows_the_limit_and_fails_above_it_with_metrics(self):
        for slowdown, limit, expected in (
            (15.0, 115.0, (0, "success", "passed")),
            (14.9, 114.9, (1, "failed", "regressed")),
        ):
            with self.subTest(max_slowdown_pct=slowdown):
                code, record, _, _, call = self.invoke_with_baseline(
                    baseline_json(p95_ms=100.0, max_slowdown_pct=slowdown),
                    result=completed_run(latency_scale=11.5),
                )
                self.assertEqual((code, record["status"], record["regression"]["status"]), expected)
                self.assertEqual(record["latency_context"], LATENCY_CONTEXT)
                self.assertEqual(record["regression"]["limit_p95_ms"], limit)
                self.assertEqual(record["regression"]["observed_p95_ms"], 115.0)
                self.assertEqual(record["latency_ms"]["p95"], 115.0)
                self.assertEqual(record["measured_query_count"], 750)
                self.assertEqual(len(record["raw_latencies_ms"]), 750)
                self.assertIn("first_measured_round_rankings", record)
                call.assert_awaited_once()

    def test_missing_or_invalid_baseline_fails_before_measurement(self):
        for case, contents in (
            ("missing file", None),
            ("malformed JSON", "{"),
            ("commit", baseline_json(baseline_commit="main")),
            ("numeric commit", baseline_json(baseline_commit=int("1" * 40))),
            ("infinite p95", baseline_json(p95_ms=float("inf"))),
            ("zero slowdown", baseline_json(max_slowdown_pct=0)),
            ("boolean slowdown", baseline_json(max_slowdown_pct=True)),
        ):
            with self.subTest(case=case):
                code, record, _, _, call = self.invoke_with_baseline(contents)
                self.assertEqual((code, record["status"]), (1, "failed"))
                self.assertEqual(record["regression"]["status"], "invalid_baseline")
                self.assertNotIn("latency_ms", record)
                call.assert_not_called()

    def test_incompatible_baseline_fails_with_metrics(self):
        for section, key, value in (
            ("workload", "top_k", 10),
            ("runner", "machine", "arm64"),
        ):
            with self.subTest(section=section):
                context = {**LATENCY_CONTEXT, section: {**LATENCY_CONTEXT[section], key: value}}
                code, record, _, _, call = self.invoke_with_baseline(baseline_json(compatibility=context))
                self.assertEqual((code, record["status"]), (1, "failed"))
                self.assertEqual(record["regression"]["status"], "incompatible_baseline")
                self.assertEqual(record["latency_context"], LATENCY_CONTEXT)
                self.assertEqual(record["latency_ms"]["p95"], 10.0)
                self.assertEqual(len(record["raw_latencies_ms"]), 750)
                call.assert_awaited_once()

    def test_competitor_agreement_is_reported_without_failing_a_low_score(self):
        queries = run_ci.get_queries()
        digest = WORKLOAD["dataset_sha256"]
        rows = [
            {"id": f"doc-{i}", "text": f"Template {i // 5} (variant {i}, context 0)"}
            for i in range(10)
        ]
        competitor_ids = [row["id"] for row in rows[:5]]
        reference = make_reference(
            digest, queries,
            {engine: {q: competitor_ids for q in queries} for engine in ("pinecone", "qdrant", "chroma")},
            {"pinecone": "llama-text-embed-v2", "qdrant": "BAAI/bge-small-en-v1.5", "chroma": "all-MiniLM-L6-v2"},
        )
        run = completed_run()
        run.configuration["dataset_sha256"] = digest
        run.measurement.rankings = {q: [row["id"] for row in rows[5:]] for q in queries}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "competitor-reference.json"
            path.write_text(json.dumps(reference), encoding="utf-8")
            with patch.object(run_ci, "load_fixed_documents", return_value=(rows, digest)):
                code, record, _, _, call = self.invoke(result=run, args=("--competitor-reference", str(path)))

        self.assertEqual((code, record["status"], record["quality"]["status"]), (0, "success", "measured"))
        self.assertIsNone(record["quality"]["recall"])
        self.assertEqual(record["quality"]["competitor_agreement"]["mean_agreement"], 0.0)
        self.assertEqual(record["quality"]["competitor_agreement"]["scored_queries"], 15)
        self.assertEqual(record["latency_ms"]["p95"], 10.0)
        call.assert_awaited_once()

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
