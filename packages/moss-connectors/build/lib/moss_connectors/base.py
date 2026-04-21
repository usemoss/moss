"""Core shapes every connector and caller uses.

A Record is the normalized row a connector yields. A DocumentMapping tells the
ingester how to turn each Record into a Moss DocumentInfo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Sequence


@dataclass
class Record:
    """A single row read from a source. `fields` is the raw column -> value map."""

    id: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentMapping:
    """How to project a Record onto a Moss document.

    text: either a field name to pull from `Record.fields`, or a function that
        builds the text from the whole record (e.g. concatenating columns).
    metadata: list of field names to copy into the document's metadata. Values
        are stringified because Moss metadata is Dict[str, str].
    id: field name to use as the document id. Defaults to Record.id itself
        when set to "id".
    embedding: optional field name holding a pre-computed vector (Sequence[float]).
        Set this when ingesting from a vector database (Pinecone, Qdrant, etc.)
        that already carries embeddings you want to reuse.
    """

    text: str | Callable[[Record], str]
    metadata: list[str] | None = None
    id: str = "id"
    embedding: str | None = None


class Connector(ABC):
    """Subclass this and implement `read()` to add a new source."""

    @abstractmethod
    def read(self) -> Iterator[Record]:
        """Yield every record that should be ingested. Runs once, then stops."""
        raise NotImplementedError
