"""Tests for the Strands Agents Moss integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from strands_agents_moss import MossSearchTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_search_result(docs=None):
    """Create a mock SearchResult."""
    result = MagicMock()
    result.docs = docs or []
    result.time_taken_ms = 2.5
    return result


def _make_mock_doc(text="sample text", score=0.95, doc_id="doc-1", metadata=None):
    """Create a mock DocumentInfo."""
    doc = MagicMock()
    doc.text = text
    doc.score = score
    doc.id = doc_id
    doc.metadata = metadata or {}
    return doc


# ---------------------------------------------------------------------------
# MossSearchTool – unit tests
# ---------------------------------------------------------------------------


class TestMossSearchToolInit:
    """Tests for MossSearchTool initialization."""

    def test_default_values(self):
        """Verify default parameter values on construction."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        assert tool._index_name == "idx"
        assert tool._top_k == 5
        assert tool._alpha == 0.8
        assert tool._tool_name == "moss_search"
        assert tool._index_loaded is False

    def test_custom_values(self):
        """Verify custom parameter values are stored."""
        tool = MossSearchTool(
            project_id="pid",
            project_key="pkey",
            index_name="idx",
            tool_name="custom_search",
            tool_description="Custom desc",
            top_k=10,
            alpha=0.5,
        )
        assert tool._tool_name == "custom_search"
        assert tool._tool_description == "Custom desc"
        assert tool._top_k == 10
        assert tool._alpha == 0.5

    def test_tool_property_returns_strands_tool(self):
        """Verify the tool property returns a Strands DecoratedFunctionTool."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        t = tool.tool
        assert t is not None
        assert hasattr(t, "tool_name") or callable(t)


class TestMossSearchToolLoadIndex:
    """Tests for load_index."""

    @pytest.mark.asyncio
    async def test_load_index_sets_flag(self):
        """Verify load_index delegates to client and sets the loaded flag."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        with patch.object(tool._client, "load_index", new_callable=AsyncMock) as mock_load:
            await tool.load_index()
            mock_load.assert_called_once_with("idx")
            assert tool._index_loaded is True

    @pytest.mark.asyncio
    async def test_load_index_only_loads_once(self):
        """Verify concurrent load_index calls only trigger one actual load."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        with patch.object(tool._client, "load_index", new_callable=AsyncMock) as mock_load:
            await tool.load_index()
            await tool.load_index()
            mock_load.assert_called_once()


class TestMossSearchToolSearch:
    """Tests for the search method."""

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self):
        """Verify search formats multiple docs with scores."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        tool._index_loaded = True

        docs = [
            _make_mock_doc("First result", 0.95, "d1"),
            _make_mock_doc("Second result", 0.80, "d2"),
        ]
        mock_result = _make_mock_search_result(docs)

        with patch.object(tool._client, "query", new_callable=AsyncMock, return_value=mock_result):
            output = await tool.search("test query")
            assert "First result" in output
            assert "Second result" in output
            assert "score=0.950" in output
            assert "score=0.800" in output

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Verify empty results produce a 'no results' message."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        tool._index_loaded = True

        mock_result = _make_mock_search_result([])
        with patch.object(tool._client, "query", new_callable=AsyncMock, return_value=mock_result):
            output = await tool.search("test query")
            assert "No relevant results found" in output

    @pytest.mark.asyncio
    async def test_search_raises_if_index_not_loaded(self):
        """Verify search raises RuntimeError before load_index is called."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        with pytest.raises(RuntimeError, match="not loaded"):
            await tool.search("test query")

    @pytest.mark.asyncio
    async def test_search_with_metadata_source(self):
        """Verify source metadata is included in formatted output."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        tool._index_loaded = True

        docs = [_make_mock_doc("doc text", 0.9, "d1", {"source": "faq.md"})]
        mock_result = _make_mock_search_result(docs)

        with patch.object(tool._client, "query", new_callable=AsyncMock, return_value=mock_result):
            output = await tool.search("q")
            assert "source=faq.md" in output


# ---------------------------------------------------------------------------
# Tool invocation – tests that actually call the Strands tool
# ---------------------------------------------------------------------------


def _make_tool_use(query: str, tool_use_id: str = "test-123") -> dict:
    """Create a Strands ToolUse dict for invoking a tool via .stream()."""
    return {
        "toolUseId": tool_use_id,
        "name": "moss_search",
        "input": {"query": query},
    }


async def _invoke_tool(tool_fn, query: str) -> str:
    """Invoke a Strands tool via .stream() and return the result text."""
    tool_use = _make_tool_use(query)
    result_text = ""
    async for chunk in tool_fn.stream(tool_use, {}):
        if chunk.get("type") == "tool_result":
            content = chunk["tool_result"].get("content", [])
            for part in content:
                if "text" in part:
                    result_text += part["text"]
    return result_text


class TestToolInvocation:
    """Tests that invoke the Strands tool function directly."""

    @pytest.mark.asyncio
    async def test_tool_invocation_returns_string(self):
        """Verify invoking the tool returns a formatted string, not a Future."""
        moss = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        moss._index_loaded = True

        docs = [_make_mock_doc("Tool result", 0.88, "d1")]
        mock_result = _make_mock_search_result(docs)

        with patch.object(moss._client, "query", new_callable=AsyncMock, return_value=mock_result):
            output = await _invoke_tool(moss.tool, "test")
            assert isinstance(output, str)
            assert "Tool result" in output
            assert "score=0.880" in output

    @pytest.mark.asyncio
    async def test_tool_invocation_error_when_not_loaded(self):
        """Verify tool invocation returns an error result when index not loaded."""
        moss = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )

        tool_use = _make_tool_use("test")
        async for chunk in moss.tool.stream(tool_use, {}):
            if chunk.get("type") == "tool_result":
                assert chunk["tool_result"]["status"] == "error"
                error_text = chunk["tool_result"]["content"][0]["text"]
                assert "not loaded" in error_text

    @pytest.mark.asyncio
    async def test_tool_invocation_empty_results(self):
        """Verify tool invocation with no matching docs."""
        moss = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        moss._index_loaded = True

        mock_result = _make_mock_search_result([])
        with patch.object(moss._client, "query", new_callable=AsyncMock, return_value=mock_result):
            output = await _invoke_tool(moss.tool, "nothing")
            assert isinstance(output, str)
            assert "No relevant results found" in output


# ---------------------------------------------------------------------------
# Format results – edge cases
# ---------------------------------------------------------------------------


class TestFormatResults:
    """Tests for _format_results edge cases."""

    def test_format_with_no_documents(self):
        """Verify empty doc list returns fallback message."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        result = tool._format_results([])
        assert "No relevant results found" in result

    def test_format_with_custom_prefix(self):
        """Verify custom result_prefix is used in output."""
        tool = MossSearchTool(
            project_id="pid",
            project_key="pkey",
            index_name="idx",
            result_prefix="Search results:\n\n",
        )
        docs = [_make_mock_doc("hello", 0.99)]
        result = tool._format_results(docs)
        assert result.startswith("Search results:")
        assert "hello" in result

    def test_format_numbers_results(self):
        """Verify docs are numbered sequentially starting at 1."""
        tool = MossSearchTool(
            project_id="pid", project_key="pkey", index_name="idx"
        )
        docs = [
            _make_mock_doc("first", 0.9),
            _make_mock_doc("second", 0.8),
            _make_mock_doc("third", 0.7),
        ]
        result = tool._format_results(docs)
        assert "1. first" in result
        assert "2. second" in result
        assert "3. third" in result
