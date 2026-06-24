"""DynamoDB source connector for Moss.

from moss_connector_dynamodb import DynamoDBConnector, DynamoDBQueryConnector, ingest
"""

from .connector import DynamoDBConnector, DynamoDBQueryConnector
from .ingest import ingest

__all__ = ["DynamoDBConnector", "DynamoDBQueryConnector", "ingest"]
