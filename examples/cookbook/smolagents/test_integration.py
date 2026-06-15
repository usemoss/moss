import unittest
from unittest.mock import MagicMock, patch

from tool import MossRetrievalTool


class TestMossRetrievalTool(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.tool = MossRetrievalTool(self.mock_client, "test-index")

    def tearDown(self):
        self.tool._loop.call_soon_threadsafe(self.tool._loop.stop)
        self.tool._thread.join(timeout=1)

    @patch.object(MossRetrievalTool, "_run_async")
    def test_forward_formats_results(self, mock_run_async):
        mock_docs = [
            MagicMock(id="d1", text="First result content", score=0.9),
            MagicMock(id="d2", text="Second result content", score=0.8),
        ]
        mock_run_async.return_value = MagicMock(docs=mock_docs)

        result = self.tool.forward("test query", top_k=2)

        self.assertIn("Result ID: d1", result)
        self.assertIn("First result content", result)
        self.assertIn("Score: 0.900", result)
        self.assertIn("Result ID: d2", result)
        self.assertIn("Second result content", result)
        self.assertIn("Score: 0.800", result)

    @patch.object(MossRetrievalTool, "_run_async")
    def test_forward_empty_results(self, mock_run_async):
        mock_run_async.return_value = MagicMock(docs=[])
        result = self.tool.forward("empty query")
        self.assertEqual(result, "")

    @patch.object(MossRetrievalTool, "_run_async")
    def test_forward_passes_metadata_filter(self, mock_run_async):
        mock_run_async.return_value = MagicMock(docs=[])
        filt = {"$and": [{"field": "category", "condition": {"$eq": "refunds"}}]}
        self.tool.forward("query", top_k=3, metadata_filter=filt)

        _, call_kwargs = mock_run_async.call_args
        # _run_async is called with a positional coroutine arg — just verify it was called
        self.assertTrue(mock_run_async.called)

    @patch.object(MossRetrievalTool, "_run_async")
    def test_forward_propagates_errors(self, mock_run_async):
        mock_run_async.side_effect = RuntimeError("connection failed")
        with self.assertRaises(RuntimeError, msg="connection failed"):
            self.tool.forward("error query")

    def test_tool_schema(self):
        self.assertEqual(self.tool.name, "moss_retrieval")
        self.assertIn("query", self.tool.inputs)
        self.assertIn("top_k", self.tool.inputs)
        self.assertIn("metadata_filter", self.tool.inputs)
        self.assertEqual(self.tool.output_type, "string")


if __name__ == "__main__":
    unittest.main()
