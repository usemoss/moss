"""Offline tests for the ten-moss session manager."""

import asyncio
import importlib.util
import pathlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ten_moss import DocumentInfo, MossSessionConfig, MossSessionManager


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
    session.get_docs = AsyncMock(return_value=list(docs))
    session.delete_docs = AsyncMock(return_value=None)
    session.push_index = AsyncMock()
    session.doc_count = doc_count
    return session


class TestMossSessionConfig(unittest.TestCase):
    """MossSessionConfig defaults and overrides."""

    def test_defaults(self):
        cfg = MossSessionConfig()
        self.assertEqual(cfg.moss_project_id, "")
        self.assertEqual(cfg.moss_index_name, "")
        self.assertEqual(cfg.moss_model_id, "")  # unspecified: adopt stored/SDK default
        self.assertEqual(cfg.moss_top_k, 5)
        self.assertEqual(cfg.moss_alpha, 0.8)
        self.assertEqual(cfg.moss_max_context_chars, 2000)
        self.assertEqual(cfg.moss_context_header, "Relevant knowledge from Moss:")
        self.assertTrue(cfg.enable_moss)

    def test_project_key_is_masked_in_repr(self):
        cfg = MossSessionConfig(moss_project_key="super-secret")
        self.assertNotIn("super-secret", repr(cfg))
        self.assertEqual(cfg.moss_project_key.get_secret_value(), "super-secret")

    def test_overrides(self):
        cfg = MossSessionConfig(moss_index_name="idx", moss_top_k=3, enable_moss=False)
        self.assertEqual(cfg.moss_index_name, "idx")
        self.assertEqual(cfg.moss_top_k, 3)
        self.assertFalse(cfg.enable_moss)

    def test_rejects_invalid_top_k_and_alpha(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            MossSessionConfig(moss_top_k=0)
        with self.assertRaises(ValidationError):
            MossSessionConfig(moss_alpha=2.0)


class TestSessionManager(unittest.IsolatedAsyncioTestCase):
    """MossSessionManager behavior with a mocked Moss client + session."""

    def _manager(self, cls, session=None, **kw):
        client = cls.return_value
        session = session if session is not None else _mock_session()
        client.session = AsyncMock(return_value=session)
        mgr = MossSessionManager(project_id="p", project_key="k", index_name="idx", **kw)
        return mgr, client, session

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_open_omits_unspecified_model_id(self, cls):
        mgr, client, session = self._manager(cls)  # no model_id -> unspecified
        await mgr.open()
        client.session.assert_awaited_once_with(index_name="idx")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_open_passes_model_id_when_set(self, cls):
        mgr, client, session = self._manager(cls, model_id="moss-mediumlm")
        await mgr.open()
        client.session.assert_awaited_once_with(index_name="idx", model_id="moss-mediumlm")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_open_rejects_custom_model(self, cls):
        mgr, client, session = self._manager(cls, model_id="custom")
        with self.assertRaises(ValueError):
            await mgr.open()
        client.session.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_before_open_is_blank(self, cls):
        mgr, client, session = self._manager(cls)
        self.assertEqual(await mgr.query_context("q"), "")
        session.query.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_formats_results(self, cls):
        session = _mock_session(docs=[_Doc("first"), _Doc("second")])
        mgr, client, session = self._manager(cls, session=session)
        await mgr.open()
        out = await mgr.query_context("q")
        self.assertIn("[1] first", out)
        self.assertIn("[2] second", out)

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_empty_results_blank(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.open()
        self.assertEqual(await mgr.query_context("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_blank_query_skips_query(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.open()
        self.assertEqual(await mgr.query_context("   "), "")
        session.query.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_swallows_exception(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.open()
        session.query = AsyncMock(side_effect=RuntimeError("boom"))
        self.assertEqual(await mgr.query_context("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_times_out_to_blank(self, cls):
        mgr, client, session = self._manager(cls, timeout_s=0.01)
        await mgr.open()

        async def _slow(*a, **k):
            await asyncio.sleep(0.1)
            return MagicMock(docs=[_Doc("late")])

        session.query = AsyncMock(side_effect=_slow)
        self.assertEqual(await mgr.query_context("q"), "")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_add_docs_delegates_to_session(self, cls):
        mgr, client, session = self._manager(cls)
        await mgr.open()
        doc = DocumentInfo(id="turn-1", text="a duplicate charge")
        await mgr.add_docs([doc])
        session.add_docs.assert_awaited_once_with([doc])

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_add_docs_before_open_is_noop(self, cls):
        mgr, client, session = self._manager(cls)
        self.assertIsNone(await mgr.add_docs([DocumentInfo(id="1", text="x")]))
        session.add_docs.assert_not_awaited()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_get_docs_delegates_to_session(self, cls):
        session = _mock_session(docs=[_Doc("x")])
        mgr, client, session = self._manager(cls, session=session)
        await mgr.open()
        docs = await mgr.get_docs()
        self.assertEqual(len(docs), 1)
        session.get_docs.assert_awaited_once()

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_push_index_returns_result(self, cls):
        mgr, client, session = self._manager(cls)
        session.push_index = AsyncMock(return_value={"job_id": "j1"})
        await mgr.open()
        result = await mgr.push_index()
        session.push_index.assert_awaited_once()
        self.assertEqual(result, {"job_id": "j1"})

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_doc_count_reflects_session(self, cls):
        session = _mock_session(doc_count=7)
        mgr, client, session = self._manager(cls, session=session)
        self.assertEqual(mgr.doc_count, 0)  # before open
        await mgr.open()
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
        self.assertTrue(mgr._enabled)

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_from_config_unwraps_secret_key(self, cls):
        cfg = MossSessionConfig(moss_project_id="p", moss_project_key="k", moss_index_name="idx")
        MossSessionManager.from_config(cfg)
        # The plain (unwrapped) key must reach the client, not a SecretStr repr.
        cls.assert_called_once_with("p", "k")

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_query_context_respects_char_budget(self, cls):
        session = _mock_session(docs=[_Doc("x" * 5000)])
        mgr, client, session = self._manager(cls, session=session, max_context_chars=100)
        await mgr.open()
        out = await mgr.query_context("q")
        self.assertIn("Relevant knowledge from Moss:", out)
        self.assertLess(len(out), 300)  # 5000-char doc was truncated to the budget

    @patch("ten_moss.moss_session_manager.MossClient")
    async def test_disabled_config_no_client_and_noop(self, cls):
        cfg = MossSessionConfig(
            moss_project_id="p", moss_project_key="k", moss_index_name="idx", enable_moss=False
        )
        mgr = MossSessionManager.from_config(cfg)
        cls.assert_not_called()  # no client constructed when disabled
        await mgr.open()  # no-op
        self.assertEqual(await mgr.query_context("q"), "")
        self.assertEqual(mgr.doc_count, 0)


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
