"""Offline tests for the ten-moss helper package."""

import unittest

from ten_moss import MossRetrievalConfig


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


if __name__ == "__main__":
    unittest.main()
