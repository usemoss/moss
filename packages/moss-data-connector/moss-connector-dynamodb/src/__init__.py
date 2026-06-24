"""DynamoDB source connector for Moss.

Provides ``DynamoDBConnector`` (Scan-based) and ``DynamoDBQueryConnector`` (Query-based)
along with the ``ingest`` helper for loading DynamoDB items into a Moss index.
See the README for usage examples.
"""

from .connector import DynamoDBConnector, DynamoDBQueryConnector
from .ingest import ingest

__all__ = ["DynamoDBConnector", "DynamoDBQueryConnector", "ingest"]
