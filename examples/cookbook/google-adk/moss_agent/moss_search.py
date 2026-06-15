"""Moss semantic search as a Google ADK tool.

Exposes ``make_moss_search`` which returns a ``(load_index, moss_search)``
pair bound to a Moss index. Pass ``moss_search`` directly into
``Agent(tools=[...])``; ADK wraps callables in ``FunctionTool`` automatically.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from moss import MossClient, QueryOptions

__all__ = ["make_moss_search"]


def make_moss_search(
    *,
    index_name: str,
    project_id: str | None = None,
    project_key: str | None = None,
    top_k: int = 5,
    alpha: float = 0.8,
) -> tuple[Callable[[], Awaitable[None]], Callable[[str], Awaitable[str]]]:
    """Build a (load_index, moss_search) pair bound to a Moss index.

    ``moss_search`` lazy-loads the index on first call, so passing it
    straight into ``Agent(tools=[...])`` is safe. Optionally ``await
    load_index()`` once at startup to avoid paying the load cost on the
    first turn.
    """
    client = MossClient(
        project_id=project_id or os.getenv("MOSS_PROJECT_ID"),
        project_key=project_key or os.getenv("MOSS_PROJECT_KEY"),
    )
    loaded = False

    async def load_index() -> None:
        nonlocal loaded
        if loaded:
            return
        await client.load_index(index_name)
        loaded = True

    async def moss_search(query: str) -> str:
        """Search the knowledge base using semantic search.

        Args:
            query: The user's question or search query.

        Returns:
            A formatted string of the most relevant documents, or a short
            message if nothing matches.
        """
        if not loaded:
            await load_index()
        result = await client.query(
            index_name, query, options=QueryOptions(top_k=top_k, alpha=alpha)
        )
        return _format_results(result.docs)

    return load_index, moss_search


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
