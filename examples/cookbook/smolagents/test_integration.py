import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from tool import MossRetrievalTool

class TestMossRetrievalTool(unittest.TestCase):
    """Unit tests for MossRetrievalTool using mocks."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.tool = MossRetrievalTool(self.mock_client, "test-index")

    @patch('tool.asyncio.run')
    def test_forward_formats_results(self, mock_asyncio_run):
        # Setup mock results
        mock_docs = [
            MagicMock(id="d1", text="First result content", score=0.9),
            MagicMock(id="d2", text="Second result content", score=0.8),
        ]
        mock_asyncio_run.return_value = MagicMock(docs=mock_docs)

        # Execute tool
        result = self.tool.forward("test query", top_k=2)

        # Verify formatting
        self.assertIn("Result ID: d1", result)
        self.assertIn("First result content", result)
        self.assertIn("Score: 0.900", result)
        self.assertIn("Result ID: d2", result)
        self.assertIn("Second result content", result)
        self.assertIn("Score: 0.800", result)

    @patch('tool.asyncio.run')
    def test_forward_empty_results(self, mock_asyncio_run):
        # Setup mock empty results
        mock_asyncio_run.return_value = MagicMock(docs=[])

        # Execute tool
        result = self.tool.forward("empty query")

        # Verify output - currently it returns an empty string join
        self.assertEqual(result, "")

    @patch('tool.asyncio.run')
    def test_forward_error_handling(self, mock_asyncio_run):
        # Setup mock error
        mock_asyncio_run.side_effect = RuntimeError("Something went wrong")

        # Execute and verify it raises
        with self.assertRaises(RuntimeError):
            self.tool.forward("error query")

    @patch('tool.asyncio.run')
    def test_forward_running_loop_error(self, mock_asyncio_run):
        # Simulate asyncio.run() failing due to existing loop
        mock_asyncio_run.side_effect = RuntimeError("asyncio.run() cannot be called from a running event loop")

        with self.assertRaises(RuntimeError) as cm:
            self.tool.forward("loop query")
        
        self.assertIn("running event loop", str(cm.exception))
        self.assertIn("Jupyter notebook", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
