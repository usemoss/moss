"""Copy rows into a Moss index."""

from __future__ import annotations

from collections.abc import Iterable

from moss import DocumentInfo, MossClient, MutationResult


async def ingest(
    source: Iterable[DocumentInfo],
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: str | None = None,
) -> MutationResult | None:
    """Copy every `DocumentInfo` from `source` into a fresh Moss index."""
    docs = list(source)
    if not docs:
        return None
    client = MossClient(project_id, project_key)
    return await client.create_index(index_name, docs, model_id=model_id)
