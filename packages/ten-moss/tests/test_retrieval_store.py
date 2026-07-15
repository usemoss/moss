"""Offline tests for the ten-moss helper package."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ten_moss import MossRetrievalConfig, MossRetrievalStore


class _Doc:
    """Minimal stand-in for a Moss QueryResultDocumentInfo."""

    def __init__(self, text, score=0.0, id="d", metadata=None):
        self.text = text
        self.score = score
        self.id = id
        self.metadata = metadata or {}


class TestMossRetrievalConfig(unittest.TestCase):
    """MossRetrievalConfig defaults and overrides."""

    def test_defaults(self):
        cfg = MossRetrievalConfig()
        self.assertEqual(cfg.moss_project_id, "")
        self.assertEqual(cfg.moss_project_key, "")
        self.assertEqual(cfg.moss_index_name, "")
        self.assertEqual(cfg.moss_top_k, 5)
        self.assertEqual(cfg.moss_alpha, 0.8)
        self.assertEqual(cfg.moss_context_header, "Relevant knowledge from Moss:")
        self.assertTrue(cfg.enable_moss)

    def test_overrides(self):
        cfg = MossRetrievalConfig(
            moss_project_id="p", moss_index_name="idx", moss_top_k=3, enable_moss=False
        )
        self.assertEqual(cfg.moss_project_id, "p")
        self.assertEqual(cfg.moss_index_name, "idx")
        self.assertEqual(cfg.moss_top_k, 3)
        self.assertFalse(cfg.enable_moss)


class TestFormatContext(unittest.TestCase):
    """MossRetrievalStore.format_context formatting."""

    def _store(self, **kw):
        with patch("ten_moss.moss_retrieval_store.MossClient"):
            return MossRetrievalStore(project_id="p", project_key="k", index_name="idx", **kw)

    def test_formats_numbered_passages_under_header(self):
        store = self._store(context_header="Knowledge:")
        out = store.format_context([_Doc("alpha"), _Doc("beta")])
        self.assertIn("Knowledge:", out)
        self.assertIn("[1] alpha", out)
        self.assertIn("[2] beta", out)

    def test_strips_whitespace_in_passages(self):
        store = self._store()
        out = store.format_context([_Doc("  spaced  ")])
        self.assertIn("[1] spaced", out)


class TestRetrieve(unittest.IsolatedAsyncioTestCase):
    """MossRetrievalStore.load / retrieve behavior with a mocked MossClient."""

    def _store_with_mock(self, mock_client_cls, **kw):
        mock_client = mock_client_cls.return_value
        mock_client.load_index = AsyncMock(return_value="ok")
        mock_client.query = AsyncMock(return_value=MagicMock(docs=[]))
        store = MossRetrievalStore(project_id="p", project_key="k", index_name="idx", **kw)
        return store, mock_client

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_load_calls_load_index_once(self, cls):
        store, client = self._store_with_mock(cls)
        await store.load()
        client.load_index.assert_awaited_once_with("idx")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_maps_results_to_context(self, cls):
        store, client = self._store_with_mock(cls)
        client.query = AsyncMock(return_value=MagicMock(docs=[_Doc("first"), _Doc("second")]))
        out = await store.retrieve("q")
        self.assertIn("[1] first", out)
        self.assertIn("[2] second", out)

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_empty_results_returns_blank(self, cls):
        store, client = self._store_with_mock(cls)
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_blank_query_skips_client(self, cls):
        store, client = self._store_with_mock(cls)
        self.assertEqual(await store.retrieve("   "), "")
        client.query.assert_not_awaited()

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_swallows_exception(self, cls):
        store, client = self._store_with_mock(cls)
        client.query = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_retrieve_times_out_to_blank(self, cls):
        store, client = self._store_with_mock(cls, timeout_s=0.01)

        async def _slow(*a, **k):
            await asyncio.sleep(0.1)
            return MagicMock(docs=[_Doc("late")])

        client.query = AsyncMock(side_effect=_slow)
        self.assertEqual(await store.retrieve("q"), "")

    @patch("ten_moss.moss_retrieval_store.MossClient")
    async def test_from_config_builds_store(self, cls):
        cfg = MossRetrievalConfig(
            moss_project_id="p",
            moss_project_key="k",
            moss_index_name="idx",
            moss_top_k=7,
            moss_alpha=0.5,
            moss_context_header="H",
        )
        store = MossRetrievalStore.from_config(cfg)
        self.assertEqual(store._index_name, "idx")
        self.assertEqual(store._top_k, 7)
        self.assertEqual(store._alpha, 0.5)
        self.assertEqual(store._context_header, "H")


if __name__ == "__main__":
    unittest.main()
