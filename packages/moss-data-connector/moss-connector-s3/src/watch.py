"""Keep a Moss index in sync with an S3 bucket.

``watch()`` ingests the bucket once, then polls it and rebuilds the index
whenever the bucket contents change. Change detection compares
``{key: etag}`` snapshots from ``S3Connector.snapshot()``, so added,
removed, and modified objects all trigger a re-index. Snapshots only list
keys — object bodies are downloaded only when a re-index actually runs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

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

    Args:
        source: The ``S3Connector`` to read from.
        project_id: Moss project id.
        project_key: Moss project key.
        index_name: Name of the Moss index to (re)create.
        poll_interval: Seconds to wait between bucket snapshots.
        model_id: Optional Moss model id, forwarded to ``ingest``.
        auto_id: Forwarded to ``ingest``; replaces mapper ids with UUIDs.
        on_change: Optional callback invoked after each re-index with the
            new ``{key: etag}`` snapshot.
        max_polls: Stop after this many polls (useful for tests and one-shot
            sync jobs). ``None`` (the default) polls until cancelled.

    Returns:
        The number of re-indexes performed (not counting the initial ingest).
    """
    previous = source.snapshot()
    await ingest(source, project_id, project_key, index_name, model_id=model_id, auto_id=auto_id)

    reindexed = 0
    polls = 0
    while max_polls is None or polls < max_polls:
        await asyncio.sleep(poll_interval)
        polls += 1
        current = source.snapshot()
        if current == previous:
            continue
        await ingest(
            source, project_id, project_key, index_name, model_id=model_id, auto_id=auto_id
        )
        reindexed += 1
        previous = current
        if on_change is not None:
            maybe_coro = on_change(current.copy())
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
    return reindexed
