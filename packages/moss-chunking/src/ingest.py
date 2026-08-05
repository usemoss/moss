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
    """Create a Moss index holding exactly these chunks.

    This is the create path only: it builds a fresh index every time, so it is
    not what you reach for to refresh one document inside an existing one — that
    is `MossClient.add_docs`, and it is where the contract's stable IDs earn
    their keep, because re-chunking an unchanged document reproduces the same
    IDs and replaces those chunks rather than appending a second copy.

    Deliberately without the connector template's `auto_id` option, for the same
    reason: random UUIDs would make every chunk look new on the way back in.
    """
    docs = list(documents)
    if not docs:
        return None
    client = MossClient(project_id, project_key)
    return await client.create_index(index_name, docs, model_id=model_id)
