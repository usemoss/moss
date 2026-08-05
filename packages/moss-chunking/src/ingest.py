"""Copy chunks into a Moss index."""

from __future__ import annotations

from collections.abc import Iterable

from moss import (
    DocumentInfo,
    GetDocumentsOptions,
    MossClient,
    MutationOptions,
    MutationResult,
)

from .chunk import MAX_CHUNK_INDEX, chunk_id

#: How many candidate IDs to look up at once when hunting for a source's leftover
#: chunks. One round trip covers a document that shrank by up to this many chunks,
#: which is nearly all of them.
_PROBE_WINDOW = 256


async def ingest(
    documents: Iterable[DocumentInfo],
    project_id: str,
    project_key: str,
    index_name: str,
    model_id: str | None = None,
) -> MutationResult | None:
    """Create a Moss index holding exactly these chunks.

    This is the create path only: it builds a fresh index every time, so it is
    not what you reach for to refresh one document inside an existing one — use
    `refresh_source` for that.

    Deliberately without the connector template's `auto_id` option: random UUIDs
    would make every chunk look new on the way back in, where the contract's
    stable IDs let an unchanged document reproduce exactly the IDs it had.
    """
    docs = list(documents)
    if not docs:
        return None
    client = MossClient(project_id, project_key)
    return await client.create_index(index_name, docs, model_id=model_id)


async def refresh_source(
    client: MossClient,
    index_name: str,
    source: str,
    documents: Iterable[DocumentInfo],
) -> MutationResult | None:
    """Replace everything `index_name` holds for `source` with `documents`.

    Stable IDs make re-chunking an unchanged document a no-op and a rewritten one
    an overwrite — but only for the chunks that still exist. `add_docs` upserts,
    it does not reconcile: if `notes.md` used to cut into 21 chunks and now cuts
    into 6, `#chunk-0006` through `#chunk-0020` stay in the index, still
    searchable, holding text that is no longer in the document. Nothing errors,
    and the stale hits look exactly like real ones.

    So the tail is deleted before the new chunks go in. What makes finding it
    cheap is the contract itself: `chunk_document` guarantees indices run
    `0, 1, 2, …`, so anything left over sits in a contiguous run above the new
    chunk count, and looking up one window of candidate IDs past the end is
    enough to find it or prove it is not there.

    Passing no documents deletes every chunk for `source`, which is how a deleted
    file is removed from the index.

    `upsert` is set explicitly rather than left to the server's default, since
    replacing a chunk in place is the entire premise of the ID contract.
    """
    docs = list(documents)

    stale: list[str] = []
    start = len(docs)
    while start <= MAX_CHUNK_INDEX:
        window = [
            chunk_id(source, index)
            for index in range(start, min(start + _PROBE_WINDOW, MAX_CHUNK_INDEX + 1))
        ]
        found = await client.get_docs(index_name, GetDocumentsOptions(doc_ids=window))
        if not found:
            break
        stale.extend(doc.id for doc in found)
        start += len(window)

    if stale:
        # Batched, because the stale run can be thousands of IDs long and a
        # single request carrying all of them is a request that can fail all of
        # them.
        for offset in range(0, len(stale), _PROBE_WINDOW):
            await client.delete_docs(index_name, stale[offset : offset + _PROBE_WINDOW])

    if not docs:
        return None
    return await client.add_docs(index_name, docs, MutationOptions(upsert=True))
