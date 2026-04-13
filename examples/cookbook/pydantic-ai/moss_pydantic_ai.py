"""Cookbook example: use Moss semantic search as a Pydantic AI tool.

This module provides a reusable ``MossSearchTool`` class and a convenience
``as_tool()`` helper.  Copy this file into your own project, or install the
cookbook as a package with ``pip install -e .``
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from typing import Any

from moss import MossClient, QueryOptions
from pydantic_ai import Tool

__all__ = ["MossSearchTool", "as_tool"]

logger = logging.getLogger("moss_pydantic_ai")


# ---------------------------------------------------------------------------
# Core adapter
# ---------------------------------------------------------------------------


class MossSearchTool:
    """Moss semantic search exposed as a Pydantic AI tool.

    Manages the :class:`MossClient` lifecycle and exposes a ``.tool``
    property returning a :class:`pydantic_ai.Tool` ready to be passed
    to ``Agent(tools=[...])``.

    Usage::

        from moss import MossClient
        from moss_pydantic_ai import MossSearchTool

        client = MossClient("pid", "pkey")
        moss = MossSearchTool(client=client, index_name="my-index")
        await moss.load_index()

        agent = Agent("openai:gpt-4o", tools=[moss.tool])
    """

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
        """Initialize with a shared MossClient and retrieval settings.

        Args:
            client: A pre-built :class:`MossClient` instance.
            index_name: Name of the Moss index to query.
            tool_name: Name exposed to the LLM for tool selection.
            tool_description: Description exposed to the LLM.  If ``None``
                a sensible default is used.
            top_k: Number of results to retrieve per query.
            alpha: Blend between semantic (1.0) and keyword (0.0) scoring.
        """
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

    # -- public API ---------------------------------------------------------

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
        """Query the Moss index and return formatted results.

        Args:
            query: Natural-language search text.

        Returns:
            Formatted string of search results suitable for LLM context.

        Raises:
            RuntimeError: If :meth:`load_index` has not been called.
        """
        if not self._index_loaded:
            raise RuntimeError(
                f"Index '{self._index_name}' not loaded. "
                "Call 'await moss_tool.load_index()' first."
            )

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

    # -- internals ----------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Convenience helper
# ---------------------------------------------------------------------------


def as_tool(
    *,
    client: MossClient,
    index_name: str,
    tool_name: str = "moss_search",
    tool_description: str | None = None,
    top_k: int = 5,
    alpha: float = 0.8,
) -> tuple[MossSearchTool, Tool]:
    """Create a ``MossSearchTool`` and return ``(instance, tool)``.

    This is a shortcut when you only need the tool object for ``Agent(tools=[...])``.
    You still need to call ``await instance.load_index()`` before running the agent.

    Example::

        moss, tool = as_tool(client=client, index_name="docs")
        await moss.load_index()
        agent = Agent("openai:gpt-4o", tools=[tool])
    """
    moss = MossSearchTool(
        client=client,
        index_name=index_name,
        tool_name=tool_name,
        tool_description=tool_description,
        top_k=top_k,
        alpha=alpha,
    )
    return moss, moss.tool


# ---------------------------------------------------------------------------
# Runnable demo
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def main() -> None:
    """Run an interactive example using the Moss-backed search tool."""
    from dotenv import load_dotenv
    from pydantic_ai import Agent

    load_dotenv()

    client = MossClient(
        _require_env("MOSS_PROJECT_ID"),
        _require_env("MOSS_PROJECT_KEY"),
    )
    moss = MossSearchTool(
        client=client,
        index_name=_require_env("MOSS_INDEX_NAME"),
    )
    await moss.load_index()

    agent = Agent(
        _require_env("PYDANTIC_AI_MODEL"),
        system_prompt=(
            "Answer user questions with the help of Moss search when "
            "factual lookup from the knowledge base is needed."
        ),
        tools=[moss.tool],
    )

    question = os.getenv(
        "PYDANTIC_AI_PROMPT",
        "What does the knowledge base say about refunds?",
    )
    result = await agent.run(question)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
