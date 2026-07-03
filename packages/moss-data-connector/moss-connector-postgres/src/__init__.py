"""PostgreSQL source connector for Moss.

    from moss_connector_postgres import PostgresConnector, ingest
"""

from .connector import PostgresConnector
from .ingest import ingest

__all__ = ["PostgresConnector", "ingest"]
