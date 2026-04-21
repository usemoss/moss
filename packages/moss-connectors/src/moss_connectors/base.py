"""Shared config type used by `ingest()`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocumentMapping:
    """How to turn a row (dict) into a Moss document.

    All four fields are column names in the source row.

    id: column holding the document id.
    text: column holding the text to index.
    metadata: columns to copy onto the document as metadata (values are stringified).
    embedding: column holding a pre-computed vector (list[float]).
        Use this when ingesting from a vector DB that already has embeddings.
    """

    id: str
    text: str
    metadata: list[str] | None = None
    embedding: str | None = None
