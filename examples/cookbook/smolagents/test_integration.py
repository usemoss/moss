"""Tests for the smolagents + Moss cookbook integration.

All tests use a mocked MossClient - no Moss credentials required.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from moss_smolagents import MossSearchTool


def _mock_search_result(docs=None):
    """Create a mock SearchResult."""
    result = MagicMock()
    result.docs = docs or []
    result.time_taken_ms = 1.5
    return result


def _mock_doc(text="sample text", score=0.95, doc_id="d1", metadata=None):
    """Create a mock QueryResultDocumentInfo."""
    doc = MagicMock()
    doc.text = text
    doc.score = score
    doc.id = doc_id
    doc.metadata = metadata or {}
    return doc


class TestMossSearchToolInit(unittest.TestCase):
    """Construction and default values."""

    @patch("moss_smolagents.MossClient")
    def test_defaults(self, mock_client_cls):
        client = mock_client_cls.return_value
        tool = MossSearchTool(client=client, index_name="idx")
        self.assertEqual(tool._index_name, "idx")
        self.assertEqual(tool._top_k, 5)
        self.assertAlmostEqual(tool._alpha, 0.8)
        self.assertEqual(tool.name, "moss_search")
        self.assertEqual(tool.output_type, "string")
        self.assertIn("query", tool.inputs)

    @patch("moss_smolagents.MossClient")
    def test_custom_values(self, mock_client_cls):
        client = mock_client_cls.return_value
        tool = MossSearchTool(
            client=client,
            index_name="idx",
            tool_name="custom_search",
            top_k=10,
            alpha=0.5,
        )
        self.assertEqual(tool.name, "custom_search")
        self.assertEqual(tool._top_k, 10)
        self.assertAlmostEqual(tool._alpha, 0.5)

    def test_missing_client_and_credentials(self):
        with self.assertRaises(ValueError):
            MossSearchTool(index_name="idx")


class TestLoadIndex(unittest.IsolatedAsyncioTestCase):
    """Tests for load_index()."""

    async def test_load_index_calls_client(self):
        client = MagicMock()
        client.load_index = AsyncMock()
        tool = MossSearchTool(client=client, index_name="idx")

        await tool.load_index()

        client.load_index.assert_awaited_once_with("idx")


class TestForward(unittest.TestCase):
    """Tests for forward() sync wrapper execution."""

    def test_forward_calls_query_and_formats_results(self):
        client = MagicMock()
        client.load_index = AsyncMock()
        client.query = AsyncMock(
            return_value=_mock_search_result(
                [
                    _mock_doc("first result", 0.9, "d1"),
                    _mock_doc("second result", 0.7, "d2"),
                ]
            )
        )
        tool = MossSearchTool(client=client, index_name="idx")

        output = tool.forward("test query")

        client.query.assert_called_once()
        self.assertIn("first result", output)
        self.assertIn("second result", output)
        self.assertIn("score=0.900", output)
        self.assertIn("score=0.700", output)

    def test_forward_empty_results(self):
        client = MagicMock()
        client.query = AsyncMock(return_value=_mock_search_result([]))
        tool = MossSearchTool(client=client, index_name="idx")

        output = tool.forward("empty query")

        self.assertEqual(output, "No relevant results found.")

    def test_forward_includes_metadata_source(self):
        client = MagicMock()
        client.query = AsyncMock(
            return_value=_mock_search_result(
                [_mock_doc("doc text", 0.85, "d1", {"source": "faq.md"})]
            )
        )
        tool = MossSearchTool(client=client, index_name="idx")

        output = tool.forward("q")

        self.assertIn("source=faq.md", output)


if __name__ == "__main__":
    unittest.main()
