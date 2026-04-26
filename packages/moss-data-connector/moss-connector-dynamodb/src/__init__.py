"""DynamoDB source connector for Moss."""

from .connector import DynamoDBConnector
from .ingest import ingest

__all__ = ["DynamoDBConnector", "ingest"]
