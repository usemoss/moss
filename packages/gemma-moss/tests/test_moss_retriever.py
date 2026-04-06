"""Tests for MossRetriever."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemma_moss.moss_retriever import MossRetriever


class TestMossRetriever:
    """Tests for MossRetriever."""

    def _make_retriever(self, **kwargs) -> MossRetriever:
        """Create a retriever with mocked MossClient."""
        defaults = {
            "project_id": "test-project",
            "project_key": "test-key",
            "index_name": "test-index",
        }
        defaults.update(kwargs)
        with patch("gemma_moss.moss_retriever.MossClient"):
            return MossRetriever(**defaults)

    @pytest.mark.asyncio
    async def test_query_before_load_raises(self):
        """Raise RuntimeError if query is called before load_index."""
        retriever = self._make_retriever()
        with pytest.raises(RuntimeError, match="not loaded"):
            await retriever.query("test query")

    @pytest.mark.asyncio
    async def test_retrieve_before_load_raises(self):
        """Raise RuntimeError if retrieve is called before load_index."""
        retriever = self._make_retriever()
        with pytest.raises(RuntimeError, match="not loaded"):
            await retriever.retrieve("test query")

    @pytest.mark.asyncio
    async def test_load_index(self):
        """Load index delegates to MossClient."""
        retriever = self._make_retriever()
        retriever._client.load_index = AsyncMock()

        await retriever.load_index()

        retriever._client.load_index.assert_awaited_once_with("test-index")

    @pytest.mark.asyncio
    async def test_query_returns_search_result(self):
        """Query returns raw SearchResult from MossClient."""
        retriever = self._make_retriever()
        retriever._index_loaded = True

        mock_result = MagicMock()
        mock_result.docs = []
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.query("test query")

        assert result is mock_result
        retriever._client.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_retrieve_returns_formatted_string(self):
        """Retrieve returns formatted string from the formatter."""
        doc = MagicMock()
        doc.text = "Test document"
        doc.metadata = {}
        doc.score = 0.9

        mock_result = MagicMock()
        mock_result.docs = [doc]

        retriever = self._make_retriever()
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result is not None
        assert "Test document" in result

    @pytest.mark.asyncio
    async def test_retrieve_returns_none_for_empty_results(self):
        """Retrieve returns None when no documents match."""
        mock_result = MagicMock()
        mock_result.docs = []

        retriever = self._make_retriever()
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_custom_formatter(self):
        """Retrieve uses a custom formatter when provided."""
        doc = MagicMock()
        doc.text = "Hello"
        doc.metadata = {}

        mock_result = MagicMock()
        mock_result.docs = [doc]

        custom_formatter = MagicMock(return_value="custom output")

        retriever = self._make_retriever(formatter=custom_formatter)
        retriever._index_loaded = True
        retriever._client.query = AsyncMock(return_value=mock_result)

        result = await retriever.retrieve("test query")

        assert result == "custom output"
        custom_formatter.assert_called_once_with([doc])

    @pytest.mark.asyncio
    async def test_custom_top_k_and_alpha(self):
        """Query passes top_k and alpha to MossClient."""
        retriever = self._make_retriever(top_k=3, alpha=0.5)
        retriever._index_loaded = True

        mock_result = MagicMock()
        mock_result.docs = []
        retriever._client.query = AsyncMock(return_value=mock_result)

        await retriever.query("test")

        call_args = retriever._client.query.call_args
        options = call_args[1].get("options")
        if options is None and len(call_args[0]) > 2:
            options = call_args[0][2]
        assert options.top_k == 3
        assert options.alpha == 0.5
