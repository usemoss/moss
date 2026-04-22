"""Moss + Agora Conversational AI integration.

Exposes Moss semantic search as an MCP tool over streamable HTTP, suitable
for use as an ``llm.mcp_servers`` entry in Agora ConvoAI's REST ``join`` body.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from moss import MossClient, QueryOptions


@dataclass
class AgoraSearchResult:
    """Result of a Moss search, serialized for the MCP tool output."""

    documents: list[dict[str, Any]]
    time_taken_ms: int | None = None


class MossAgoraSearch:
    """Moss search adapter exposed as an MCP tool.

    Raises ordinary Python exceptions from Moss. MCP-error translation happens
    inside :func:`create_mcp_app`, not here.
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
    ) -> None:
        """Initialize the adapter with Moss credentials and index-query defaults."""
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._index_loaded = False

    async def load_index(self) -> None:
        """Preload the configured index. Idempotent."""
        if self._index_loaded:
            return
        await self._client.load_index(self._index_name)
        self._index_loaded = True

    async def search(self, query: str) -> AgoraSearchResult:
        """Run a semantic search against the preloaded index."""
        if not self._index_loaded:
            raise RuntimeError(f"Index {self._index_name!r} not loaded. Call load_index() first.")
        options = QueryOptions(top_k=self._top_k, alpha=self._alpha)
        result = await self._client.query(self._index_name, query, options=options)
        return AgoraSearchResult(
            documents=self._format_results(result.docs),
            time_taken_ms=result.time_taken_ms,
        )

    @staticmethod
    def _format_results(documents: Sequence[Any]) -> list[dict[str, Any]]:
        """Format Moss ``DocumentInfo`` objects as a list of serializable dicts.

        Each doc becomes ``{"content": doc.text, "similarity": doc.score}``.
        """
        return [{"content": doc.text, "similarity": doc.score} for doc in documents]


def create_mcp_app(search: MossAgoraSearch) -> FastMCP:
    """Build a FastMCP server exposing ``search_knowledge_base`` over streamable HTTP.

    The server awaits ``search.load_index()`` in its lifespan before accepting
    tool calls. Exceptions from ``search.search()`` are re-raised as
    ``RuntimeError`` with a readable message so FastMCP serializes them as
    MCP tool-errors (this is the single exception-to-tool-error boundary).
    """

    @asynccontextmanager
    async def lifespan(_app: FastMCP):
        await search.load_index()
        yield

    app = FastMCP("agora-moss", lifespan=lifespan)

    @app.tool()
    async def search_knowledge_base(query: str) -> list[dict[str, Any]]:
        """Search the configured Moss knowledge base and return matching documents."""
        try:
            result = await search.search(query)
        except Exception as e:
            raise RuntimeError(f"Moss search failed: {e}") from e
        return result.documents

    return app
