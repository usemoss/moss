"""Copy chunks into a Moss index."""

from __future__ import annotations

from collections.abc import Iterable

from moss import DocumentInfo, MossClient, MutationResult


async def ingest(
    documents: Iterable[DocumentInfo],
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: str | None = None,
) -> MutationResult | None:
    """Copy every chunk into a fresh Moss index.

    Deliberately without the connector template's `auto_id` option: random UUIDs
    would defeat the contract's stable IDs, and re-indexing an unchanged document
    would append duplicates instead of replacing what is already there.
    """
    docs = list(documents)
    if not docs:
        return None
    client = MossClient(project_id, project_key)
    return await client.create_index(index_name, docs, model_id=model_id)
