"""Credential-free checks for the fixed workload and local Moss benchmark."""

import hashlib
import importlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
bench_moss = importlib.import_module("bench_moss")
corpus = importlib.import_module("corpus")
local_moss = importlib.import_module("local_moss")


def hits(*ids):
    return SimpleNamespace(docs=[SimpleNamespace(id=doc_id) for doc_id in ids])


class FixedCorpusTests(unittest.TestCase):
    def test_checked_in_corpus_matches_the_pinned_workload(self):
        rows, digest = corpus.load_fixed_documents()
        self.assertEqual(len(rows), 100_000)
        self.assertEqual(digest, corpus.FIXED_CORPUS_SHA256)

    def test_changed_bytes_are_rejected_for_the_fixed_corpus(self):
        raw = b'[{"id":"a","text":"example"}]'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_bytes(raw + b"\n")
            with (
                patch.multiple(
                    corpus, FIXED_CORPUS_PATH=path, FIXED_CORPUS_SHA256=hashlib.sha256(raw).hexdigest()
                ),
                self.assertRaisesRegex(ValueError, "checksum"),
            ):
                corpus.load_fixed_documents(expected_count=1)

    def test_short_and_duplicate_corpora_are_rejected(self):
        row = {"id": "a", "text": "example"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            for rows, message in (([row], "exactly 2"), ([row, row], "unique")):
                with self.subTest(message=message):
                    path.write_text(json.dumps(rows), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        corpus.load_fixed_documents(path, expected_count=2)


class MeasurementTests(unittest.IsolatedAsyncioTestCase):
    async def test_measures_only_queries_and_keeps_the_first_measured_ranking(self):
        durations = iter([77, 6, 2])
        calls = []
        timing = False

        @contextmanager
        def timer():
            nonlocal timing
            timing = True
            try:
                yield SimpleNamespace(elapsed_ms=next(durations))
            finally:
                timing = False

        class Hit:
            @property
            def id(self):
                if timing:
                    raise AssertionError("Hit validation must be outside query timing")
                return "a" if len(calls) == 3 else "b"

        async def query(_):
            calls.append(timing)
            return SimpleNamespace(docs=[Hit()])

        with (
            patch.multiple(bench_moss, TOP_K=1, WARMUP_ROUNDS=1, QUERY_ROUNDS=2, Timer=timer),
            redirect_stdout(io.StringIO()),
        ):
            measured = await bench_moss.measure_queries(
                query, ["q"], name="test", expected_ids={"a", "b"}
            )

        self.assertEqual(calls, [True, False, True, True])
        self.assertEqual(measured.first_query_ms, 77)
        self.assertEqual(measured.latencies_ms, [6, 2])
        self.assertEqual(measured.rankings, {"q": ["a"]})

    async def test_validates_hits_after_the_first_measured_round(self):
        good = hits("a", "b")
        with (
            patch.multiple(bench_moss, TOP_K=2, WARMUP_ROUNDS=0, QUERY_ROUNDS=2),
            redirect_stdout(io.StringIO()),
        ):
            for invalid in (hits("a"), hits("a", "a"), hits("a", "outside")):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    await bench_moss.measure_queries(
                        AsyncMock(side_effect=[good, good, invalid]),
                        ["q"],
                        name="test",
                        expected_ids={"a", "b"},
                    )

    async def test_legacy_runner_returns_latency_stats_for_the_loaded_index(self):
        client = SimpleNamespace(
            get_index=AsyncMock(),
            load_index=AsyncMock(),
            query=AsyncMock(return_value=hits("a")),
        )
        sdk = SimpleNamespace(
            MossClient=Mock(return_value=client), DocumentInfo=Mock(), QueryOptions=SimpleNamespace
        )
        with (
            patch.dict(sys.modules, {"moss": sdk, "dotenv": SimpleNamespace(load_dotenv=Mock())}),
            patch.dict("os.environ", {"MOSS_INDEX_NAME": "example-index"}, clear=True),
            patch.multiple(bench_moss, WARMUP_ROUNDS=0, QUERY_ROUNDS=1),
            redirect_stdout(io.StringIO()),
        ):
            result = await bench_moss.run_async()

        client.load_index.assert_awaited_once_with("example-index")
        self.assertIsInstance(result, bench_moss.BenchmarkResult)
        self.assertEqual(result.count, len(corpus.get_queries()))


class LocalBuilderTests(unittest.IsolatedAsyncioTestCase):
    async def test_closes_session_and_client_when_index_build_fails(self):
        failure = RuntimeError("index build failed")
        session = MagicMock(doc_count=0, add_docs=AsyncMock(side_effect=failure))
        session.__aenter__.return_value = session
        client = MagicMock(session=AsyncMock(return_value=session))
        client.__aenter__.return_value = client
        sdk = SimpleNamespace(MossClient=Mock(return_value=client), QueryOptions=SimpleNamespace)
        with (
            patch.dict(sys.modules, {"moss": sdk}),
            patch.object(
                local_moss, "load_fixed_documents",
                return_value=([{"id": "doc-0", "text": "passage"}], "corpus-sha"),
            ),
            self.assertRaisesRegex(RuntimeError, "index build failed"),
        ):
            await local_moss.run_local_async("test-project", "test-key")

        for resource in (session, client):
            resource.__aexit__.assert_awaited_once()
            self.assertIs(resource.__aexit__.await_args.args[1], failure)

    async def test_builds_full_corpus_before_querying_without_cloud_autoload(self):
        rows = [{"id": f"doc-{i}", "text": f"passage {i}"} for i in range(7)]
        indexed = []
        session = MagicMock(doc_count=0, model_id="moss-minilm")
        session.__aenter__.return_value = session
        client = MagicMock(session=AsyncMock(return_value=session))
        client.__aenter__.return_value = client
        sdk = SimpleNamespace(MossClient=Mock(return_value=client), QueryOptions=SimpleNamespace)

        async def add_docs(batch):
            indexed.extend(batch)
            session.doc_count = len(indexed)
            return len(batch), 0

        async def query(_, options):
            self.assertCountEqual(indexed, rows)
            self.assertEqual((options.top_k, options.alpha), (5, 1))
            return hits(*(row["id"] for row in indexed[:options.top_k]))

        session.add_docs = AsyncMock(side_effect=add_docs)
        session.query = AsyncMock(side_effect=query)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            raw = json.dumps(rows).encode()
            path.write_bytes(raw)
            with (
                patch.dict(sys.modules, {"moss": sdk}),
                patch.object(bench_moss, "DOC_COUNT", len(rows)),
                patch.object(local_moss, "BATCH_SIZE", 3),
                redirect_stdout(io.StringIO()),
            ):
                run = await local_moss.run_local_async("test-project", "test-key", corpus_path=path)

        self.assertIs(client.session.await_args.kwargs["auto_load_on_init"], False)
        self.assertEqual(run.configuration["actual_doc_count"], len(rows))
        self.assertEqual(run.configuration["dataset_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(run.measurement.latencies_ms), 750)
        session.__aexit__.assert_awaited_once()
        client.__aexit__.assert_awaited_once()
