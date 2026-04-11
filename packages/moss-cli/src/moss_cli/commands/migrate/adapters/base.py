"""Abstract base class for migration source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class SourcePreview:
    """Summary information about a migration source."""

    doc_count: int
    dimensions: Optional[int]
    metadata_fields: List[str]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceDocument:
    """A single document from a migration source."""

    id: str
    text: str
    metadata: Optional[Dict[str, str]] = None
    embedding: Optional[List[float]] = None


class SourceAdapter(ABC):
    """Abstract base class for reading documents from an external source."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the source (validate file exists, etc.)."""
        ...

    @abstractmethod
    def preview(self) -> SourcePreview:
        """Return summary statistics without reading all data."""
        ...

    @abstractmethod
    def stream(self, batch_size: int = 1000) -> Iterator[List[SourceDocument]]:
        """Yield batches of documents from the source."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Clean up any resources."""
        ...
