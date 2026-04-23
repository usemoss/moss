from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from moss import MossClient, QueryOptions
from pydantic_ai import Tool

__all__ = ["MossSearchTool", "as_tool"]

logger = logging.getLogger("moss_pydantic_ai")


class MossSearchTool:
    """Moss semantic search exposed as a Pydantic AI tool."""

    def __init__(
        self,
        *,
        client: MossClient,
        index_name: str,
        tool_name: str = "moss_search",
        tool_description: str | None = None,
        top_k: int = 5,
        alpha: float = 0.8,
    ) -> None:
        """Initialize with a shared MossClient and retrieval settings."""
        self._client = client
        self._index_name = index_name
        self._tool_name = tool_name
        self._tool_description = tool_description or (
            "Search the knowledge base using Moss semantic search. "
            "Returns the most relevant documents for a given query."
        )
        self._top_k = top_k
        self._alpha = alpha
        self._index_loaded = False
        self._load_lock = asyncio.Lock()
        self._tool_obj = self._build_tool()

    async def load_index(self) -> None:
        """Pre-load the Moss index into memory for fast queries.

        Safe to call multiple times; only the first call triggers loading.
        """
        async with self._load_lock:
            if self._index_loaded:
                return
            logger.info("Loading Moss index '%s'", self._index_name)
            await self._client.load_index(self._index_name)
            self._index_loaded = True
            logger.info("Moss index '%s' ready", self._index_name)

    async def search(self, query: str) -> str:
        """Query the Moss index and return formatted results."""
        result = await self._client.query(
            self._index_name,
            query,
            QueryOptions(top_k=self._top_k, alpha=self._alpha),
        )
        logger.info(
            "Moss query returned %d docs in %sms",
            len(result.docs),
            result.time_taken_ms,
        )
        return self._format_results(result.docs)

    @property
    def tool(self) -> Tool:
        """Return the ``pydantic_ai.Tool`` to pass to an Agent."""
        return self._tool_obj

    def _build_tool(self) -> Tool:
        """Build a Pydantic AI Tool wrapping :meth:`search`."""
        instance = self

        async def moss_search(query: str) -> str:
            """Search the knowledge base for relevant documents.

            Args:
                query: Natural-language question or lookup text.
            """
            return await instance.search(query)

        return Tool(
            moss_search,
            takes_ctx=False,
            name=self._tool_name,
            description=self._tool_description,
        )

    @staticmethod
    def _format_results(documents: Sequence[Any]) -> str:
        """Format Moss search results into a numbered string."""
        if not documents:
            return "No relevant results found."

        lines = ["Relevant knowledge base results:", ""]
        for idx, doc in enumerate(documents, start=1):
            meta = doc.metadata or {}
            extras = []
            if source := meta.get("source"):
                extras.append(f"source={source}")
            if (score := getattr(doc, "score", None)) is not None:
                extras.append(f"score={score:.3f}")
            suffix = f" ({', '.join(extras)})" if extras else ""
            text = getattr(doc, "text", "") or ""
            lines.append(f"{idx}. {text}{suffix}")
        return "\n".join(lines)


def as_tool(
    *,
    client: MossClient,
    index_name: str,
    tool_name: str = "moss_search",
    tool_description: str | None = None,
    top_k: int = 5,
    alpha: float = 0.8,
) -> tuple[MossSearchTool, Tool]:
    """Create a ``MossSearchTool`` and return ``(instance, tool)`` as a shortcut."""
    moss = MossSearchTool(
        client=client,
        index_name=index_name,
        tool_name=tool_name,
        tool_description=tool_description,
        top_k=top_k,
        alpha=alpha,
    )
    return moss, moss.tool
