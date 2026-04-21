"""One-time data copy from external databases into Moss indexes."""

from .base import DocumentMapping
from .ingest import ingest

__all__ = ["DocumentMapping", "ingest"]
