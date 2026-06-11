import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from moss import QueryOptions
from moss_adk_tool import create_moss_tool


class TestMossADKTool(unittest.IsolatedAsyncioTestCase):
    async def test_tool_formats_results(self):
        mock_client = MagicMock()
        mock_docs = [
            MagicMock(id="doc_1", text="First result", score=0.9),
            MagicMock(id="doc_2", text="Second result", score=0.8),
        ]
        
        mock_client.query = AsyncMock()
        mock_client.query.return_value = MagicMock(docs=mock_docs)
        
        tool = create_moss_tool(mock_client, "test-index")
        
        result = await tool("test query", top_k=2)
        
        self.assertIn("Result ID: doc_1", result)
        self.assertIn("First result", result)
        self.assertIn("Score: 0.900", result)
        self.assertIn("Result ID: doc_2", result)
        self.assertIn("Second result", result)
        self.assertIn("Score: 0.800", result)
        
        mock_client.query.assert_called_once()
        args, _ = mock_client.query.call_args
        self.assertEqual(args[0], "test-index")
        self.assertEqual(args[1], "test query")

    async def test_tool_handles_empty_results(self):
        mock_client = MagicMock()
        mock_client.query = AsyncMock()
        mock_client.query.return_value = MagicMock(docs=[])
        
        tool = create_moss_tool(mock_client, "test-index")
        
        result = await tool("empty query")
        self.assertEqual(result, "No relevant information found.")

    async def test_tool_passes_metadata_filter(self):
        mock_client = MagicMock()
        mock_client.query = AsyncMock()
        mock_client.query.return_value = MagicMock(docs=[])
        
        tool = create_moss_tool(mock_client, "test-index")
        filt = {"$and": [{"field": "category", "condition": {"$eq": "refunds"}}]}
        
        await tool("query", top_k=3, metadata_filter=filt)
        
        args, kwargs = mock_client.query.call_args
        options = args[2]
        
        self.assertIsInstance(options, QueryOptions)
        self.assertEqual(options.top_k, 3)
        self.assertEqual(options.filter, filt)

if __name__ == "__main__":
    unittest.main()
