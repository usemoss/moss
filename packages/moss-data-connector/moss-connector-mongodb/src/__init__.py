"""MongoDB source connector for Moss.

    from moss_connector_mongodb import MongoDBConnector, ingest
"""

from .connector import MongoDBConnector
from .ingest import ingest

__all__ = ["MongoDBConnector", "ingest"]
