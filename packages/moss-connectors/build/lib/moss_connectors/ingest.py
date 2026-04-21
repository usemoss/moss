"""The one public entry point: `ingest()`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from moss import DocumentInfo, MutationOptions

from .base import Connector, DocumentMapping, Record

if TYPE_CHECKING:
    from moss import MossClient


def _record_to_document(record: Record, mapping: DocumentMapping) -> DocumentInfo:
    text = mapping.text(record) if callable(mapping.text) else record.fields.get(mapping.text, "")
    doc_id = record.id if mapping.id == "id" else str(record.fields[mapping.id])
    metadata = None
    if mapping.metadata:
        metadata = {k: str(record.fields[k]) for k in mapping.metadata if k in record.fields}
    embedding = record.fields.get(mapping.embedding) if mapping.embedding else None
    return DocumentInfo(id=str(doc_id), text=str(text), metadata=metadata, embedding=embedding)


async def ingest(
    connector: Connector,
    mapping: DocumentMapping,
    client: "MossClient",
    index_name: str,
    batch_size: int = 500,
) -> int:
    """Read every record from `connector`, map it, and upsert into `index_name`.

    Returns the number of documents ingested. One-shot — no incremental sync.
    Assumes the index already exists; create it first with `client.create_index`.
    """
    batch: list[DocumentInfo] = []
    total = 0
    options = MutationOptions(upsert=True)

    for record in connector.read():
        batch.append(_record_to_document(record, mapping))
        if len(batch) >= batch_size:
            await client.add_docs(index_name, batch, options)
            total += len(batch)
            batch = []

    if batch:
        await client.add_docs(index_name, batch, options)
        total += len(batch)

    return total
