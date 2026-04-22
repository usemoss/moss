"""SQLite source connector for Moss.

    from moss_connector_sqlite import SQLiteConnector, ingest
"""

from .connector import SQLiteConnector
from .ingest import ingest

__all__ = ["SQLiteConnector", "ingest"]
