"""One-shot ingestion from external databases into Moss indexes."""

from .base import Connector, DocumentMapping, Record
from .ingest import ingest

__all__ = ["Connector", "DocumentMapping", "Record", "ingest"]
