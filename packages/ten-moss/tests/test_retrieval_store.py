"""Offline tests for the ten-moss helper package."""

import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
