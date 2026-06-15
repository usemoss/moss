"""Tests for the Semantic Kernel Moss plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from semantic_kernel_moss import MossPlugin

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
# MossPlugin – init tests
# ---------------------------------------------------------------------------


class TestMossPluginInit:
    """Tests for MossPlugin initialization."""

    def test_default_values(self):
        """Verify default parameter values on construction."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        assert plugin._index_name == "idx"
        assert plugin._top_k == 5
        assert plugin._alpha == 0.8
        assert plugin._index_loaded is False

    def test_custom_values(self):
        """Verify custom parameter values are stored."""
        plugin = MossPlugin(
            project_id="pid",
            project_key="pkey",
            index_name="idx",
            top_k=10,
            alpha=0.5,
        )
        assert plugin._top_k == 10
        assert plugin._alpha == 0.5


# ---------------------------------------------------------------------------
# MossPlugin – load_index tests
# ---------------------------------------------------------------------------


class TestMossPluginLoadIndex:
    """Tests for load_index."""

    @pytest.mark.asyncio
    async def test_load_index_sets_flag(self):
        """Verify load_index delegates to client and sets the loaded flag."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        with patch.object(plugin._client, "load_index", new_callable=AsyncMock) as mock_load:
            await plugin.load_index()
            mock_load.assert_called_once_with("idx")
            assert plugin._index_loaded is True

    @pytest.mark.asyncio
    async def test_load_index_only_loads_once(self):
        """Verify concurrent load_index calls only trigger one actual load."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        with patch.object(plugin._client, "load_index", new_callable=AsyncMock) as mock_load:
            await plugin.load_index()
            await plugin.load_index()
            mock_load.assert_called_once()


# ---------------------------------------------------------------------------
# MossPlugin – search tests
# ---------------------------------------------------------------------------


class TestMossPluginSearch:
    """Tests for the search method."""

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self):
        """Verify search formats multiple docs with scores."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        plugin._index_loaded = True

        docs = [
            _make_mock_doc("First result", 0.95, "d1"),
            _make_mock_doc("Second result", 0.80, "d2"),
        ]
        mock_result = _make_mock_search_result(docs)

        with patch.object(
            plugin._client, "query", new_callable=AsyncMock, return_value=mock_result
        ):
            output = await plugin.search("test query")
            assert "First result" in output
            assert "Second result" in output
            assert "score=0.950" in output
            assert "score=0.800" in output

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Verify empty results produce a 'no results' message."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        plugin._index_loaded = True

        mock_result = _make_mock_search_result([])
        with patch.object(
            plugin._client, "query", new_callable=AsyncMock, return_value=mock_result
        ):
            output = await plugin.search("test query")
            assert "No relevant results found" in output

    @pytest.mark.asyncio
    async def test_search_raises_if_index_not_loaded(self):
        """Verify search raises RuntimeError before load_index is called."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        with pytest.raises(RuntimeError, match="not loaded"):
            await plugin.search("test query")

    @pytest.mark.asyncio
    async def test_search_with_metadata_source(self):
        """Verify source metadata is included in formatted output."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        plugin._index_loaded = True

        docs = [_make_mock_doc("doc text", 0.9, "d1", {"source": "faq.md"})]
        mock_result = _make_mock_search_result(docs)

        with patch.object(
            plugin._client, "query", new_callable=AsyncMock, return_value=mock_result
        ):
            output = await plugin.search("q")
            assert "source=faq.md" in output

    @pytest.mark.asyncio
    async def test_search_propagates_client_exceptions(self):
        """Verify client exceptions bubble up without being caught."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        plugin._index_loaded = True

        with patch.object(
            plugin._client,
            "query",
            new_callable=AsyncMock,
            side_effect=ConnectionError("network failure"),
        ):
            with pytest.raises(ConnectionError, match="network failure"):
                await plugin.search("test query")


# ---------------------------------------------------------------------------
# Kernel integration tests
# ---------------------------------------------------------------------------


class TestKernelIntegration:
    """Tests that verify the plugin works with a real SK Kernel."""

    @pytest.mark.asyncio
    async def test_plugin_discoverable_by_kernel(self):
        """Verify kernel discovers the search function after add_plugin."""
        import semantic_kernel as sk

        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        kernel = sk.Kernel()
        kernel.add_plugin(plugin, plugin_name="moss")

        moss_plugin = kernel.get_plugin("moss")
        assert moss_plugin is not None
        assert "search" in moss_plugin

    @pytest.mark.asyncio
    async def test_kernel_invoke_returns_string(self):
        """Verify full round-trip: kernel.invoke returns formatted results."""
        import semantic_kernel as sk

        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        plugin._index_loaded = True

        docs = [_make_mock_doc("kernel result", 0.92, "d1")]
        mock_result = _make_mock_search_result(docs)

        kernel = sk.Kernel()
        kernel.add_plugin(plugin, plugin_name="moss")

        with patch.object(
            plugin._client, "query", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await kernel.invoke(function_name="search", plugin_name="moss", query="test")
            output = str(result)
            assert "kernel result" in output
            assert "score=0.920" in output


# ---------------------------------------------------------------------------
# Format results – edge cases
# ---------------------------------------------------------------------------


class TestFormatResults:
    """Tests for _format_results edge cases."""

    def test_format_with_no_documents(self):
        """Verify empty doc list returns fallback message."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        result = plugin._format_results([])
        assert "No relevant results found" in result

    def test_format_with_custom_prefix(self):
        """Verify custom result_prefix is used in output."""
        plugin = MossPlugin(
            project_id="pid",
            project_key="pkey",
            index_name="idx",
            result_prefix="Search results:\n\n",
        )
        docs = [_make_mock_doc("hello", 0.99)]
        result = plugin._format_results(docs)
        assert result.startswith("Search results:")
        assert "hello" in result

    def test_format_numbers_results(self):
        """Verify docs are numbered sequentially starting at 1."""
        plugin = MossPlugin(project_id="pid", project_key="pkey", index_name="idx")
        docs = [
            _make_mock_doc("first", 0.9),
            _make_mock_doc("second", 0.8),
            _make_mock_doc("third", 0.7),
        ]
        result = plugin._format_results(docs)
        assert "1. first" in result
        assert "2. second" in result
        assert "3. third" in result
