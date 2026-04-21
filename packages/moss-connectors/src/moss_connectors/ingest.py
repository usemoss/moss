"""The one public entry point: `ingest()`."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from moss import DocumentInfo, MossClient

from .base import DocumentMapping


def _row_to_document(row: dict[str, Any], mapping: DocumentMapping) -> DocumentInfo:
    metadata = {k: str(row[k]) for k in mapping.metadata} if mapping.metadata else None
    embedding = row.get(mapping.embedding) if mapping.embedding else None
    return DocumentInfo(
        id=str(row[mapping.id]),
        text=row[mapping.text],
        metadata=metadata,
        embedding=embedding,
    )


async def ingest(
    source: Iterable[dict[str, Any]],
    mapping: DocumentMapping,
    client: MossClient,
    index_name: str,
    model_id: Optional[str] = None,
) -> int:
    """Copy every row from `source` into a fresh Moss index and return the count."""
    docs = [_row_to_document(row, mapping) for row in source]
    if not docs:
        return 0
    await client.create_index(index_name, docs, model_id=model_id)
    return len(docs)
