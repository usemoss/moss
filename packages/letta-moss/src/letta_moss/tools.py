"""Plain-function tools for registering Moss archival memory with a Letta agent.

Register these directly with ``client.tools.upsert_from_function(func=...)``
so they run inside Letta's own sandboxed tool-execution environment — no
separate server process required. Configure them via the
``MOSS_PROJECT_ID`` / ``MOSS_PROJECT_KEY`` / ``MOSS_INDEX_NAME`` environment
variables (Letta injects whatever you pass through
``tool_exec_environment_variables`` at agent-creation time).

These functions are named ``moss_memory_*``, deliberately distinct from
Letta's built-in ``archival_memory_insert``/``archival_memory_search`` tools.
Pass ``include_base_tools=False`` when creating the agent so it doesn't end
up with two competing memory tool sets.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os

from .memory import MossLettaMemory

_memory: MossLettaMemory | None = None
_memory_lock = asyncio.Lock()


async def _get_memory() -> MossLettaMemory:
    """Lazily build and load the module-level ``MossLettaMemory`` singleton.

    A single instance is reused across tool calls within a sandbox process so
    ``load_index()`` (and the underlying index download) only happens once.
    Guarded by a lock so concurrent tool calls can't each construct and load
    their own instance before the first one is stored.
    """
    global _memory
    if _memory is not None:
        return _memory
    async with _memory_lock:
        if _memory is None:
            index_name = os.getenv("MOSS_INDEX_NAME")
            if not index_name:
                raise ValueError("MOSS_INDEX_NAME env var is required.")
            memory = MossLettaMemory(index_name=index_name)
            await memory.load_index()
            _memory = memory
    return _memory


async def moss_memory_insert(content: str, tags: list[str] | None = None) -> str:
    """Insert a new memory into Moss-backed archival storage.

    Args:
        content: The text content of the memory to store.
        tags: Optional list of tags to associate with the memory, usable
            later to narrow ``moss_memory_search`` results.

    Returns:
        The id of the newly inserted memory.
    """
    memory = await _get_memory()
    return await memory.insert_memory(content, tags=tags)


async def moss_memory_search(
    query: str, top_k: int = 5, tags: list[str] | None = None
) -> list[dict]:
    """Search Moss-backed archival storage for memories relevant to a query.

    Args:
        query: Natural-language query to search for.
        top_k: Maximum number of results to return.
        tags: Optional list of tags to narrow results to — a memory is kept
            if it has any of the given tags.

    Returns:
        A list of matching memories, each with ``id``, ``content``, ``tags``,
        ``metadata``, and ``score`` fields.
    """
    memory = await _get_memory()
    items = await memory.search_memory(query, top_k=top_k, tags=tags)
    return [dataclasses.asdict(item) for item in items]


async def moss_memory_delete(memory_id: str) -> None:
    """Delete a memory from Moss-backed archival storage by id.

    Args:
        memory_id: The id of the memory to delete, as returned by
            ``moss_memory_insert`` or ``moss_memory_search``.
    """
    memory = await _get_memory()
    await memory.delete_memory(memory_id)
