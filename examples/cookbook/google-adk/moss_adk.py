"""Google ADK tool adapter for Moss semantic search."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

from moss import MossClient, QueryOptions

__all__ = ["MossSearchTool"]

logger = logging.getLogger("moss_adk")


class MossSearchTool:
    """Moss semantic search as a Google ADK tool.

    Wraps a MossClient and exposes an async function suitable for passing
    directly to ``Agent(tools=[...])``. The same tool works in text mode
    and in Live (BIDI) streaming mode.

    Usage::

        from google.adk.agents import Agent
        from moss_adk import MossSearchTool

        moss = MossSearchTool(index_name="support-docs")

        agent = Agent(
            name="support",
            model="gemini-2.5-flash",
            instruction="Answer using moss_search.",
            tools=[moss.search_tool],
        )

    The index loads on the first tool call.
    """

    def __init__(
        self,
        *,
        index_name: str,
        project_id: str | None = None,
        project_key: str | None = None,
        top_k: int = 5,
        alpha: float = 0.8,
    ):
        self._client = MossClient(
            project_id=project_id or os.getenv("MOSS_PROJECT_ID"),
            project_key=project_key or os.getenv("MOSS_PROJECT_KEY"),
        )
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._index_loaded = False

    @property
    def search_tool(self):
        """Return the async function ADK should register as a tool.

        The returned function carries a docstring and type hints that ADK
        uses to build the tool schema exposed to the model.
        """
        instance = self

        async def moss_search(query: str) -> str:
            """Search the knowledge base using semantic search.

            Args:
                query: The user's question or search query.

            Returns:
                A formatted string of the most relevant documents, or a short
                message if nothing matches.
            """
            if not instance._index_loaded:
                logger.info("Loading Moss index '%s'", instance._index_name)
                await instance._client.load_index(instance._index_name)
                instance._index_loaded = True
            result = await instance._client.query(
                instance._index_name,
                query,
                options=QueryOptions(top_k=instance._top_k, alpha=instance._alpha),
            )
            return _format_results(result.docs)

        return moss_search


def _format_results(documents: Sequence[Any]) -> str:
    if not documents:
        return "No relevant results found."
    lines = []
    for idx, doc in enumerate(documents, start=1):
        text = getattr(doc, "text", "") or ""
        score = getattr(doc, "score", None)
        suffix = f" (score={score:.3f})" if score is not None else ""
        lines.append(f"{idx}. {text}{suffix}")
    return "\n".join(lines)
