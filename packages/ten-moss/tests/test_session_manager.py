"""Offline tests for the ten-moss session manager."""

import asyncio
import importlib.util
import pathlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ten_moss import MossSessionConfig, MossSessionManager


class _Doc:
    """Minimal stand-in for a Moss query result document."""

    def __init__(self, text, score=0.0, id="d", metadata=None):
        self.text = text
        self.score = score
        self.id = id
        self.metadata = metadata or {}


def _mock_session(docs=(), doc_count=0):
    session = MagicMock()
    session.query = AsyncMock(return_value=MagicMock(docs=list(docs)))
    session.add_docs = AsyncMock(return_value=(1, 0))
    session.push_index = AsyncMock()
    session.doc_count = doc_count
    return session


class TestMossSessionConfig(unittest.TestCase):
    """MossSessionConfig defaults and overrides."""

    def test_defaults(self):
        cfg = MossSessionConfig()
        self.assertEqual(cfg.moss_project_id, "")
        self.assertEqual(cfg.moss_index_name, "")
        self.assertEqual(cfg.moss_model_id, "moss-minilm")
        self.assertEqual(cfg.moss_top_k, 5)
        self.assertEqual(cfg.moss_alpha, 0.8)
        self.assertEqual(cfg.moss_context_header, "Relevant knowledge from Moss:")
        self.assertTrue(cfg.enable_moss)

    def test_overrides(self):
        cfg = MossSessionConfig(moss_index_name="idx", moss_top_k=3, enable_moss=False)
        self.assertEqual(cfg.moss_index_name, "idx")
        self.assertEqual(cfg.moss_top_k, 3)
        self.assertFalse(cfg.enable_moss)


class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    """MossSessionManager behavior with a mocked Moss client + session."""

    def _manager(self, cls, session=None, **kw):
        client = cls.return_value
        session = session if session is not None else _mock_session()
        client.session = AsyncMock(return_value=session)
        mgr = MossSessionManager(project_id="p", project_key="k", index_name="idx", **kw)
        return mgr, client, session

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_start_opens_session(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        client.session.assert_awaited_once_with(index_name="idx", model_id="moss-minilm")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_before_start_is_blank(self, cls):
        mgr, client, session = self._manager(cls)
        self.assertEqual(await mgr.context_for("q"), "")
        session.query.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_formats_results(self, cls):
        session = _mock_session(docs=[_Doc("first"), _Doc("second")])
        mgr, client, session = self._manager(cls, session=session)
        await mgr.start()
        out = await mgr.context_for("q")
        self.assertIn("[1] first", out)
        self.assertIn("[2] second", out)

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_empty_results_blank(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        self.assertEqual(await mgr.context_for("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_blank_query_skips_query(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        self.assertEqual(await mgr.context_for("   "), "")
        session.query.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_swallows_exception(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        session.query = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertEqual(await mgr.context_for("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_context_for_times_out_to_blank(self, cls):
        mgr, client, session = self._manager(cls, timeout_s=0.01)
        await mgr.start()

        async def _slow(*a, **k):
            await asyncio.sleep(0.1)
            return MagicMock(docs=[_Doc("late")])

        session.query = AsyncMock(side_effect=_slow)
        self.assertEqual(await mgr.context_for("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_remember_adds_doc(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        await mgr.remember("customer mentioned a duplicate charge")
        session.add_docs.assert_awaited_once()
        (docs,), _ = session.add_docs.call_args
        self.assertEqual(docs[0].text, "customer mentioned a duplicate charge")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_remember_blank_is_noop(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        await mgr.remember("   ")
        session.add_docs.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_persist_pushes_index(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.start()
        await mgr.persist()
        session.push_index.assert_awaited_once()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_doc_count_reflects_session(self, cls):
        session = _mock_session(doc_count=7)
        mgr, client, session = self._manager(cls, session=session)
        self.assertEqual(mgr.doc_count, 0)  # before start
        await mgr.start()
        self.assertEqual(mgr.doc_count, 7)

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_from_config_builds_manager(self, cls):
        cfg = MossSessionConfig(
            moss_project_id="p",
            moss_project_key="k",
            moss_index_name="idx",
            moss_model_id="moss-mediumlm",
            moss_top_k=7,
            moss_alpha=0.5,
            moss_context_header="H",
        )
        mgr = MossSessionManager.from_config(cfg)
        self.assertEqual(mgr._index_name, "idx")
        self.assertEqual(mgr._model_id, "moss-mediumlm")
        self.assertEqual(mgr._top_k, 7)
        self.assertEqual(mgr._alpha, 0.5)
        self.assertEqual(mgr._context_header, "H")


class TestCreateIndexExample(unittest.TestCase):
    """The example script exposes a testable build_documents()."""

    def _load_example(self):
        path = pathlib.Path(__file__).parent.parent / "examples" / "create_index.py"
        spec = importlib.util.spec_from_file_location("_ten_moss_create_index", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_build_documents_returns_ten_docs(self):
        module = self._load_example()
        docs = module.build_documents()
        self.assertEqual(len(docs), 10)
        self.assertTrue(all(d.text for d in docs))
        self.assertEqual(len({d.id for d in docs}), 10)  # unique ids


if __name__ == "__main__":
    unittest.main()
