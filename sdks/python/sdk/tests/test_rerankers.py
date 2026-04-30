import unittest
from unittest.mock import AsyncMock, patch

from moss_core import QueryResultDocumentInfo
from moss import RerankOptions
from moss.rerankers import (
    CohereReranker,
    _REGISTRY,
    get_reranker,
    register_reranker,
)
from moss.rerankers.base import Reranker as RerankerProtocol


class TestRerankerRegistry(unittest.TestCase):
    """Tests for the reranker registry."""

    def test_cohere_registered_by_default(self):
        self.assertIn("cohere", _REGISTRY)
        self.assertIs(_REGISTRY["cohere"], CohereReranker)

    def test_register_custom_reranker(self):
        class MyReranker:
            async def rerank(self, query, documents, top_k=None, **kwargs):
                return documents

        register_reranker("my-custom", MyReranker)
        try:
            self.assertIn("my-custom", _REGISTRY)
        finally:
            _REGISTRY.pop("my-custom", None)

    def test_get_reranker_instantiates_with_kwargs(self):
        class DummyReranker:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def rerank(self, query, documents, top_k=None, **kwargs):
                return documents

        register_reranker("dummy", DummyReranker)
        try:
            instance = get_reranker("dummy", api_key="abc", model="test-model")
            self.assertIsInstance(instance, DummyReranker)
            self.assertEqual(instance.kwargs, {"api_key": "abc", "model": "test-model"})
        finally:
            _REGISTRY.pop("dummy", None)

    def test_get_unknown_reranker_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_reranker("nonexistent")
        self.assertIn("Unknown reranker provider", str(ctx.exception))


class TestRerankOptions(unittest.TestCase):
    """Tests for RerankOptions."""

    def test_stores_provider_and_kwargs(self):
        opts = RerankOptions(provider="cohere", api_key="key", top_n=5)
        self.assertEqual(opts.provider, "cohere")
        self.assertEqual(opts.top_n, 5)
        self.assertEqual(opts.init_kwargs, {"api_key": "key"})

    def test_default_top_n(self):
        opts = RerankOptions(provider="cohere", api_key="key")
        self.assertIsNone(opts.top_n)

    def test_instance_cache_starts_empty(self):
        opts = RerankOptions(provider="cohere", api_key="key")
        self.assertIsNone(opts._instance)

    def test_multiple_kwargs_forwarded(self):
        opts = RerankOptions(
            provider="cohere", api_key="k", model="rerank-v3.5", top_n=3
        )
        self.assertEqual(opts.init_kwargs, {"api_key": "k", "model": "rerank-v3.5"})


class TestCohereRerankerProtocol(unittest.TestCase):
    """CohereReranker satisfies the Reranker protocol."""

    def test_protocol_satisfied(self):
        with patch.dict("os.environ", {"COHERE_API_KEY": "test-key"}):
            reranker = CohereReranker()
            self.assertIsInstance(reranker, RerankerProtocol)

    def test_custom_reranker_satisfies_protocol(self):
        class MyReranker:
            async def rerank(self, query, documents, top_k=None, **kwargs):
                return documents

        self.assertIsInstance(MyReranker(), RerankerProtocol)


class TestCohereReranker(unittest.IsolatedAsyncioTestCase):
    """Tests for CohereReranker instantiation and behavior."""

    def test_init_with_api_key(self):
        reranker = CohereReranker(api_key="test-key")
        self.assertEqual(reranker.api_key, "test-key")
        self.assertEqual(reranker.model, "rerank-v3.5")

    def test_init_from_env(self):
        with patch.dict("os.environ", {"COHERE_API_KEY": "env-key"}):
            reranker = CohereReranker()
            self.assertEqual(reranker.api_key, "env-key")

    def test_init_no_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                CohereReranker()
            self.assertIn("Cohere API key is required", str(ctx.exception))

    def test_init_custom_model(self):
        reranker = CohereReranker(api_key="key", model="rerank-english-v2.0")
        self.assertEqual(reranker.model, "rerank-english-v2.0")

    def test_init_accepts_kwargs(self):
        reranker = CohereReranker(api_key="key", custom_option="value")
        self.assertEqual(reranker.extra_options, {"custom_option": "value"})

    async def test_rerank_empty_documents(self):
        reranker = CohereReranker(api_key="test-key")
        result = await reranker.rerank("query", [])
        self.assertEqual(result, [])

    async def test_rerank_calls_cohere_sdk(self):
        reranker = CohereReranker(api_key="test-key")
        reranker._client = AsyncMock()

        mock_result_1 = type("Result", (), {"index": 1, "relevance_score": 0.95})()
        mock_result_2 = type("Result", (), {"index": 0, "relevance_score": 0.72})()
        mock_response = type(
            "Response", (), {"results": [mock_result_1, mock_result_2]}
        )()
        reranker._client.rerank = AsyncMock(return_value=mock_response)

        docs = [
            QueryResultDocumentInfo(id="d1", text="first doc", score=0.8),
            QueryResultDocumentInfo(id="d2", text="second doc", score=0.6),
        ]

        result = await reranker.rerank("test query", docs)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "d2")
        self.assertAlmostEqual(result[0].score, 0.95, places=2)
        self.assertEqual(result[1].id, "d1")
        self.assertAlmostEqual(result[1].score, 0.72, places=2)

        reranker._client.rerank.assert_awaited_once_with(
            model="rerank-v3.5",
            query="test query",
            documents=["first doc", "second doc"],
            top_n=2,
        )

    async def test_rerank_with_top_k(self):
        reranker = CohereReranker(api_key="test-key")
        reranker._client = AsyncMock()

        mock_result = type("Result", (), {"index": 0, "relevance_score": 0.9})()
        mock_response = type("Response", (), {"results": [mock_result]})()
        reranker._client.rerank = AsyncMock(return_value=mock_response)

        docs = [
            QueryResultDocumentInfo(id="d1", text="doc1", score=0.5),
            QueryResultDocumentInfo(id="d2", text="doc2", score=0.4),
            QueryResultDocumentInfo(id="d3", text="doc3", score=0.3),
        ]

        await reranker.rerank("query", docs, top_k=1)

        call_kwargs = reranker._client.rerank.call_args.kwargs
        self.assertEqual(call_kwargs["top_n"], 1)

    async def test_rerank_sdk_error(self):
        reranker = CohereReranker(api_key="bad-key")
        reranker._client = AsyncMock()
        reranker._client.rerank = AsyncMock(side_effect=Exception("Unauthorized"))

        docs = [QueryResultDocumentInfo(id="d1", text="doc", score=0.5)]

        with self.assertRaises(Exception) as ctx:
            await reranker.rerank("query", docs)
        self.assertIn("Unauthorized", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
