"""Offline contracts for the fixed corpus and the real local benchmark path."""

import hashlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

BENCHMARKS = Path(__file__).resolve().parents[1]
if str(BENCHMARKS) not in sys.path:
    sys.path.insert(0, str(BENCHMARKS))

bench_moss = importlib.import_module("bench_moss")
corpus = importlib.import_module("corpus")
local_moss = importlib.import_module("local_moss")


def documents(count):
    return [{"id": f"doc-{i}", "text": f"Sample passage {i}"} for i in range(count)]


class FixedCorpusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "corpus.json"

    def write(self, rows):
        raw = json.dumps(rows).encode()
        self.path.write_bytes(raw)
        return raw

    def test_reports_exact_input_digest(self):
        rows = documents(3)
        raw = self.write(rows)
        actual, digest = corpus.load_fixed_documents(self.path, expected_count=3)
        self.assertEqual(actual, rows)
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

    def test_default_corpus_rejects_changed_bytes(self):
        raw = self.write(documents(3))
        with patch.object(corpus, "FIXED_CORPUS_PATH", self.path), patch.object(
            corpus, "FIXED_CORPUS_SHA256", hashlib.sha256(raw).hexdigest()
        ):
            self.path.write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "checksum"):
                corpus.load_fixed_documents(expected_count=3)
            with self.assertRaisesRegex(ValueError, "checksum"):
                corpus.load_fixed_documents(self.path, expected_count=3)

    def test_rejects_invalid_records_instead_of_shrinking_workload(self):
        invalid = [
            ({"id": "doc-0", "text": "passage"}, 1),
            (documents(2), 3),
            (["passage"], 1),
            ([{"id": "same", "text": "first"}, {"id": "same", "text": "second"}], 2),
            ([{"id": " ", "text": "passage"}], 1),
            ([{"id": "doc-0", "text": " "}], 1),
            ([{"id": "doc-0", "text": 4}], 1),
        ]
        for rows, expected_count in invalid:
            with self.subTest(rows=rows):
                self.write(rows)
                with self.assertRaises(ValueError):
                    corpus.load_fixed_documents(self.path, expected_count=expected_count)

    def test_rejects_malformed_json(self):
        self.path.write_bytes(b"[")
        with self.assertRaises(ValueError):
            corpus.load_fixed_documents(self.path, expected_count=1)


class SharedMeasurementTests(unittest.IsolatedAsyncioTestCase):
    async def test_excludes_first_query_and_warmups_and_keeps_first_round_rankings(self):
        timed_durations = iter([77, 6, 2, 5, 1, 4, 3])
        timer_active = False
        calls = []

        class FakeTimer:
            def __enter__(self):
                nonlocal timer_active
                timer_active = True
                self.elapsed_ms = next(timed_durations)
                return self

            def __exit__(self, *_):
                nonlocal timer_active
                timer_active = False

        class Hit:
            def __init__(self, doc_id):
                self.doc_id = doc_id

            @property
            def id(self):
                if timer_active:
                    raise AssertionError("Hit validation must be outside query timing")
                return self.doc_id

        async def query(text):
            calls.append(text)
            ids = ["a", "b"] if text == "alpha" else ["b", "c"]
            if len(calls) > 5:
                ids = ["c", "a"]
            return SimpleNamespace(docs=[Hit(doc_id) for doc_id in ids])

        with patch.object(bench_moss, "WARMUP_ROUNDS", 1), patch.object(
            bench_moss, "QUERY_ROUNDS", 3
        ), patch.object(bench_moss, "TOP_K", 2), patch.object(
            bench_moss, "Timer", FakeTimer
        ), redirect_stdout(io.StringIO()):
            measured = await bench_moss.measure_queries(
                query, ["alpha", "beta"], name="fixture", expected_ids={"a", "b", "c"}
            )

        self.assertEqual(calls, ["alpha", "alpha", "beta"] + ["alpha", "beta"] * 3)
        self.assertEqual(measured.first_query_ms, 77)
        self.assertEqual(measured.latencies_ms, [6, 2, 5, 1, 4, 3])
        self.assertEqual(measured.result.count, 6)
        self.assertEqual(measured.result.p50, 3)
        self.assertEqual(measured.result.p95, 6)
        self.assertEqual(measured.result.p99, 6)
        self.assertEqual(measured.rankings, {"alpha": ["a", "b"], "beta": ["b", "c"]})

    async def test_rejects_missing_duplicate_and_unknown_query_hits(self):
        for ids in ([], ["a"], ["a", "a"], ["a", "outside"]):
            with self.subTest(ids=ids):
                async def query(_text):
                    return SimpleNamespace(docs=[SimpleNamespace(id=doc_id) for doc_id in ids])

                with patch.object(bench_moss, "TOP_K", 2), redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        await bench_moss.measure_queries(
                            query, ["alpha"], name="invalid hits", expected_ids={"a", "b"}
                        )

    async def test_refuses_an_empty_or_duplicate_query_set_before_running(self):
        calls = []

        async def query(text):
            calls.append(text)
            return SimpleNamespace(docs=[])

        for queries in ([], [""], ["alpha", "alpha"]):
            with self.subTest(queries=queries), self.assertRaises(ValueError):
                await bench_moss.measure_queries(query, queries, name="bad queries")
        self.assertEqual(calls, [])

    async def test_validates_later_rounds_after_initial_rankings_are_captured(self):
        calls = 0

        async def query(_text):
            nonlocal calls
            calls += 1
            ids = ["a", "outside"] if calls == 5 else ["a", "b"]
            return SimpleNamespace(docs=[SimpleNamespace(id=doc_id) for doc_id in ids])

        with patch.object(bench_moss, "WARMUP_ROUNDS", 0), patch.object(
            bench_moss, "QUERY_ROUNDS", 2
        ), patch.object(bench_moss, "TOP_K", 2), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "outside"):
                await bench_moss.measure_queries(
                    query, ["alpha", "beta"], name="late bad hit", expected_ids={"a", "b"}
                )
        self.assertEqual(calls, 5)


class LegacyRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_cloud_index_keeps_legacy_result_and_query_contract(self):
        hits = SimpleNamespace(docs=[SimpleNamespace(id="cloud-a"), SimpleNamespace(id="cloud-b")])
        client = SimpleNamespace(
            get_index=AsyncMock(return_value=SimpleNamespace(name="existing-index")),
            load_index=AsyncMock(return_value="existing-index"),
            query=AsyncMock(return_value=hits),
            create_index=AsyncMock(side_effect=AssertionError("Unexpected cloud index creation")),
        )
        fake_sdk = ModuleType("moss")
        fake_sdk.MossClient = Mock(return_value=client)
        fake_sdk.QueryOptions = SimpleNamespace
        fake_sdk.DocumentInfo = Mock(side_effect=AssertionError("Unexpected corpus conversion"))
        fake_dotenv = ModuleType("dotenv")
        fake_dotenv.load_dotenv = Mock(return_value=None)
        credentials = {
            "MOSS_PROJECT_ID": "fixture-project",
            "MOSS_PROJECT_KEY": "fixture-key",
            "MOSS_INDEX_NAME": "existing-index",
        }
        with (
            patch.dict(sys.modules, {"moss": fake_sdk, "dotenv": fake_dotenv}),
            patch.dict("os.environ", credentials, clear=True),
            patch.object(bench_moss, "WARMUP_ROUNDS", 1),
            patch.object(bench_moss, "QUERY_ROUNDS", 2),
            patch.object(bench_moss, "TOP_K", 2),
            patch.object(bench_moss, "get_queries", return_value=["alpha", "beta"]),
            patch.object(bench_moss, "get_documents", side_effect=AssertionError("Unexpected remote corpus fetch")) as get_documents,
            redirect_stdout(io.StringIO()),
        ):
            result = await bench_moss.run_async()

        fake_sdk.MossClient.assert_called_once_with("fixture-project", "fixture-key")
        fake_dotenv.load_dotenv.assert_called_once_with()
        client.get_index.assert_awaited_once_with("existing-index")
        client.load_index.assert_awaited_once_with("existing-index")
        self.assertIsInstance(result, bench_moss.BenchmarkResult)
        self.assertEqual(result.count, 4)
        self.assertEqual(client.query.await_count, 1 + 1 * 2 + 2 * 2)
        self.assertEqual(
            [call.args[1] for call in client.query.await_args_list],
            ["alpha", "alpha", "beta", "alpha", "beta", "alpha", "beta"],
        )
        for call in client.query.await_args_list:
            self.assertEqual(call.args[0], "existing-index")
            self.assertEqual((call.args[2].top_k, call.args[2].alpha), (2, 1))
        get_documents.assert_not_called()
        fake_sdk.DocumentInfo.assert_not_called()
        client.create_index.assert_not_awaited()


class LocalBuilderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "corpus.json"
        self.rows = documents(7)
        self.path.write_text(json.dumps(self.rows), encoding="utf-8")
        self.clients = []
        self.sessions = []

    def fake_sdk(self, failure=None):
        clients = self.clients
        sessions = self.sessions

        class FakeSession:
            """Deliberately exposes no cloud-index or snapshot operations."""

            def __init__(self):
                self.doc_count = 1 if failure == "not-empty" else 0
                self.model_id = "other-model" if failure == "model" else "moss-minilm"
                self.closed = False
                self.batches = []
                self.queries = []
                sessions.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                self.closed = True

            async def add_docs(self, batch):
                if failure == "build":
                    raise RuntimeError("injected build failure")
                self.batches.append(batch)
                self.doc_count += len(batch) + (1 if failure == "count" else 0)
                return len(batch) - (1 if failure == "added" else 0), 1 if failure == "updated" else 0

            async def query(self, text, options):
                self.queries.append((text, options.top_k, options.alpha))
                if failure == "query":
                    raise RuntimeError("injected query failure")
                return SimpleNamespace(docs=[SimpleNamespace(id="doc-0"), SimpleNamespace(id="doc-1")])

        class FakeClient:
            """Only public session construction is allowed by this test double."""

            def __init__(self, project_id, project_key, **kwargs):
                self.closed = False
                self.request = None
                clients.append(self)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                self.closed = True

            async def session(self, name, *, model_id, auto_load_on_init):
                self.request = (name, model_id, auto_load_on_init)
                if auto_load_on_init:
                    raise AssertionError("Local benchmark must not download a cloud index")
                return FakeSession()

        fake = ModuleType("moss")
        fake.MossClient = FakeClient
        fake.QueryOptions = SimpleNamespace
        return fake

    async def run_fixture(self, failure=None, project_id="test-project", project_key="test-key"):
        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"moss": self.fake_sdk(failure)}))
            for key, value in {"DOC_COUNT": 7, "TOP_K": 2, "WARMUP_ROUNDS": 1, "QUERY_ROUNDS": 2}.items():
                stack.enter_context(patch.object(bench_moss, key, value))
            stack.enter_context(patch.object(local_moss, "BATCH_SIZE", 3))
            stack.enter_context(patch.object(local_moss, "get_queries", return_value=["alpha", "beta"]))
            stack.enter_context(redirect_stdout(io.StringIO()))
            return await local_moss.run_local_async(project_id, project_key, corpus_path=self.path)

    async def test_builds_every_record_in_batches_then_runs_the_existing_workload(self):
        run = await self.run_fixture()
        session = self.sessions[0]
        client = self.clients[0]
        self.assertEqual([len(batch) for batch in session.batches], [3, 3, 1])
        self.assertEqual([row for batch in session.batches for row in batch], self.rows)
        self.assertEqual(session.doc_count, 7)
        self.assertEqual(client.request, (local_moss.LOCAL_INDEX_NAME, "moss-minilm", False))
        self.assertEqual(len(session.queries), 1 + 2 + 4)
        self.assertTrue(all((top_k, alpha) == (2, 1) for _, top_k, alpha in session.queries))
        self.assertEqual(run.measurement.result.count, 4)
        self.assertEqual(run.configuration["actual_doc_count"], 7)
        self.assertEqual(run.configuration["setup_mode"], "fresh-build")
        self.assertEqual(run.configuration["dataset_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(set(run.measurement.rankings), {"alpha", "beta"})
        self.assertTrue(session.closed)
        self.assertTrue(client.closed)

    async def test_closes_both_resources_when_setup_or_measurement_fails(self):
        for failure in ("not-empty", "build", "added", "updated", "count", "model", "query"):
            with self.subTest(failure=failure):
                with self.assertRaises((ValueError, RuntimeError)):
                    await self.run_fixture(failure=failure)
                self.assertTrue(self.clients[-1].closed)
                self.assertTrue(self.sessions[-1].closed)
                if failure != "query":
                    self.assertEqual(self.sessions[-1].queries, [])

    async def test_missing_credentials_fail_before_the_sdk_is_constructed(self):
        for project_id, project_key in (("", "key"), ("project", " "), (None, "key")):
            with self.subTest(project_id=project_id, project_key=project_key):
                with self.assertRaisesRegex(ValueError, "MOSS_PROJECT_ID"):
                    await self.run_fixture(project_id=project_id, project_key=project_key)
        self.assertEqual(self.clients, [])


if __name__ == "__main__":
    unittest.main()
