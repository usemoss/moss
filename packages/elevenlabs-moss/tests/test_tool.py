"""Tests for MossClientTool result formatting, guards, and callback handling."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from elevenlabs_moss.moss_client_tool import MossClientTool


@dataclass
class FakeDoc:
    text: str
    score: float | None = None
    metadata: dict | None = None


def make_tool(**kwargs) -> MossClientTool:
    """Helper to instantiate MossClientTool with dummy credentials for offline tests."""
    defaults = {
        "project_id": "mock_pid",
        "project_key": "mock_pkey",
        "index_name": "mock_index",
    }
    defaults.update(kwargs)
    return MossClientTool(**defaults)


class TestFormatResults:
    def test_formats_text_only(self):
        tool = make_tool(index_name="faq")
        docs = [FakeDoc(text="Answer to question")]
        result = tool._format_results(docs)
        assert result == "Relevant knowledge base results:\n\n1. Answer to question"

    def test_formats_with_source_and_score(self):
        tool = make_tool(index_name="faq")
        docs = [FakeDoc(text="Answer", score=0.9254, metadata={"source": "faq.pdf"})]
        result = tool._format_results(docs)
        expected = "Relevant knowledge base results:\n\n1. Answer (source=faq.pdf, score=0.925)"
        assert result == expected

    def test_empty_docs(self):
        tool = make_tool(index_name="faq")
        result = tool._format_results([])
        assert result == "Relevant knowledge base results:"

    def test_custom_result_prefix(self):
        tool = make_tool(index_name="faq", result_prefix="Context:\n\n")
        docs = [FakeDoc(text="Result")]
        result = tool._format_results(docs)
        assert result == "Context:\n\n1. Result"

    def test_multiple_docs_ordering(self):
        tool = make_tool(index_name="faq")
        docs = [
            FakeDoc(text="First doc", score=0.95),
            FakeDoc(text="Second doc", score=0.85),
        ]
        result = tool._format_results(docs)
        assert "1. First doc (score=0.950)" in result
        assert "2. Second doc (score=0.850)" in result


class TestSearchGuard:
    @pytest.mark.asyncio
    async def test_raises_if_index_not_loaded(self):
        tool = make_tool(index_name="test-index")
        with pytest.raises(RuntimeError, match="not loaded"):
            await tool.search("hello")

    @pytest.mark.asyncio
    async def test_successful_search_when_loaded(self):
        tool = make_tool(index_name="test-index")
        tool._index_loaded = True

        mock_result = MagicMock()
        mock_result.docs = [FakeDoc(text="Result text", score=0.9)]
        mock_result.time_taken_ms = 4.2
        tool._client.query = AsyncMock(return_value=mock_result)

        output = await tool.search("sample query")
        assert "1. Result text (score=0.900)" in output
        tool._client.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_index_marks_loaded(self):
        tool = make_tool(index_name="test-index")
        assert not tool._index_loaded
        tool._client.load_index = AsyncMock(return_value=None)
        await tool.load_index()
        assert tool._index_loaded
        tool._client.load_index.assert_awaited_once_with("test-index")


class TestRegisterAndCallback:
    def test_register_calls_client_tools(self):
        tool = make_tool(index_name="test-index", tool_name="search_kb")
        mock_client_tools = MagicMock()

        tool.register(mock_client_tools)
        mock_client_tools.register.assert_called_once_with(
            "search_kb",
            tool._callback,
            is_async=True,
        )

    @pytest.mark.asyncio
    async def test_callback_empty_query(self):
        tool = make_tool(index_name="test-index")
        assert await tool._callback({}) == "No query provided."
        assert await tool._callback({"query": "   "}) == "No query provided."

    @pytest.mark.asyncio
    async def test_callback_executes_search(self):
        tool = make_tool(index_name="test-index")
        tool.search = AsyncMock(return_value="Formatted results")

        res = await tool._callback({"query": "what is moss?"})
        assert res == "Formatted results"
        tool.search.assert_awaited_once_with("what is moss?")

    @pytest.mark.asyncio
    async def test_callback_gracefully_handles_failure(self):
        tool = make_tool(index_name="test-index")
        tool.search = AsyncMock(side_effect=Exception("API connection failure"))

        res = await tool._callback({"query": "what is moss?"})
        assert res == "Search unavailable. Please try again later."
