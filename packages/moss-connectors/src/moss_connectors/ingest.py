"""The one public entry point: `ingest()`."""

from __future__ import annotations

from typing import Iterable, Optional

from moss import DocumentInfo, MossClient


async def ingest(
    source: Iterable[DocumentInfo],
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: Optional[str] = None,
) -> int:
    """Copy every `DocumentInfo` from `source` into a fresh Moss index.

    Builds a `MossClient` internally from `project_id` and `project_key`.
    Returns the number of documents ingested.
    """
    docs = list(source)
    if not docs:
        return 0
    client = MossClient(project_id, project_key)
    await client.create_index(index_name, docs, model_id=model_id)
    return len(docs)
