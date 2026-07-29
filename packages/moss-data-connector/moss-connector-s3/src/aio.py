"""Event-loop-friendly wrapper around the shared ``ingest()``.

The template ``ingest.py`` is kept byte-identical across all connector
packages, so per-source concerns live here instead (same pattern as retry
logic per the template rules). Iterating ``S3Connector`` performs
synchronous boto3 network I/O; materializing it directly inside an async
function would block every other coroutine for the duration of the bucket
download. This wrapper materializes the source in a worker thread first,
then delegates to the shared ``ingest()`` with the already-downloaded docs.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from moss import DocumentInfo, MutationResult

from .ingest import ingest as _ingest


async def ingest(
    source: Iterable[DocumentInfo],
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: str | None = None,
    auto_id: bool = False,
) -> MutationResult | None:
    """Copy every ``DocumentInfo`` from ``source`` into a fresh Moss index.

    Same contract as the shared template ``ingest()``, but the source is
    materialized via ``asyncio.to_thread`` so S3 downloads never block the
    event loop.
    """
    docs = await asyncio.to_thread(list, source)
    return await _ingest(
        docs, project_id, project_key, index_name, model_id=model_id, auto_id=auto_id
    )
