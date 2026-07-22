"""Keep a Moss index in sync with an S3 bucket.

``watch()`` ingests the bucket once, then polls it and rebuilds the index
whenever the bucket contents change. Change detection compares
``{key: etag}`` snapshots from ``S3Connector.snapshot()``, so added,
removed, and modified objects all trigger a re-index. Snapshots only list
keys — object bodies are downloaded only when a re-index actually runs.

S3 network I/O is synchronous under the hood (``boto3``), so snapshots and
object downloads run in a worker thread via ``asyncio.to_thread`` to avoid
blocking the event loop between polls.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from moss import MossClient

from .connector import S3Connector
from .ingest import ingest


async def watch(
    source: S3Connector,
    project_id: str,
    project_key: str,
    index_name: str,
    *,
    poll_interval: float = 60.0,
    model_id: str | None = None,
    auto_id: bool = False,
    on_change: Callable[[dict[str, str]], Any] | None = None,
    max_polls: int | None = None,
) -> int:
    """Ingest the bucket into ``index_name``, then re-ingest on every change.

    The snapshot is taken *before* each ingest, so objects that change while
    an ingest is running are picked up on the next poll rather than lost.

    Every rebuild deletes the existing index and creates it afresh
    (``create_index`` is create-only), which re-embeds the whole bucket. If
    every matching object is deleted, the Moss index is deleted too, so
    stale documents never remain searchable; the index is re-created on the
    next change that adds objects back.

    Args:
        source: The ``S3Connector`` to read from.
        project_id: Moss project id.
        project_key: Moss project key.
        index_name: Name of the Moss index to (re)create.
        poll_interval: Seconds to wait between bucket snapshots.
        model_id: Optional Moss model id, forwarded to ``ingest``.
        auto_id: Forwarded to ``ingest``; replaces mapper ids with UUIDs.
        on_change: Optional callback invoked after each re-index with the
            new ``{key: etag}`` snapshot. May be sync or async.
        max_polls: Stop after this many polls (useful for tests and one-shot
            sync jobs). ``None`` (the default) polls until cancelled.

    Returns:
        The number of re-indexes performed (not counting the initial ingest).
    """
    previous = await asyncio.to_thread(source.snapshot)
    await _sync(source, project_id, project_key, index_name, model_id, auto_id, empty=False)

    reindexed = 0
    polls = 0
    while max_polls is None or polls < max_polls:
        await asyncio.sleep(poll_interval)
        polls += 1
        current = await asyncio.to_thread(source.snapshot)
        if current == previous:
            continue
        await _sync(
            source, project_id, project_key, index_name, model_id, auto_id, empty=not current
        )
        reindexed += 1
        previous = current
        if on_change is not None:
            maybe_awaitable = on_change(current.copy())
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
    return reindexed


async def _sync(
    source: S3Connector,
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: str | None,
    auto_id: bool,
    *,
    empty: bool,
) -> None:
    """Rebuild the index from the bucket, or delete it when the bucket emptied.

    ``create_index`` is create-only, so every rebuild deletes the old index
    first — including the initial one, in case a prior watch() run left the
    index behind. The delete is best-effort: not-found on a first run (or
    after an empty transition, or a concurrent external delete) is fine.

    ``ingest()`` is a no-op for an empty source, so a transition to an empty
    bucket ends after the delete — otherwise the old documents would stay
    searchable forever.
    """
    client = MossClient(project_id, project_key)
    try:
        await client.delete_index(index_name)
    except Exception:
        pass  # index does not exist yet — nothing to delete
    if empty:
        return
    # Materialize in a worker thread: iterating the connector performs
    # synchronous S3 downloads that would otherwise block the event loop.
    docs = await asyncio.to_thread(list, source)
    await ingest(docs, project_id, project_key, index_name, model_id=model_id, auto_id=auto_id)
