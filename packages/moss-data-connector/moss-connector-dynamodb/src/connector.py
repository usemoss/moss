"""DynamoDB connector.

Reads items from a DynamoDB table via ``boto3``'s ``Table.scan()``. One yielded
``DocumentInfo`` per item.

Uses the standard boto3 credential chain (env vars, shared credentials file,
IAM role, etc.). Pass ``endpoint_url`` to target DynamoDB Local or localstack
for development/testing.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

import boto3
from moss import DocumentInfo


class DynamoDBConnector:
    """Read items from a DynamoDB table and yield one ``DocumentInfo`` per item.

    By default scans the entire table. Pass ``scan_kwargs`` to restrict results
    or control which attributes come back (e.g. ``FilterExpression``,
    ``ProjectionExpression``, ``ExpressionAttributeNames``).

    ``mapper`` turns a DynamoDB item (dict) into a ``DocumentInfo``.
    """

    def __init__(
        self,
        table_name: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        region_name: str | None = None,
        endpoint_url: str | None = None,
        scan_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.table_name = table_name
        self.mapper = mapper
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.scan_kwargs = dict(scan_kwargs) if scan_kwargs else {}

    def __iter__(self) -> Iterator[DocumentInfo]:
        resource = boto3.resource(
            "dynamodb",
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
        )
        table = resource.Table(self.table_name)
        kwargs = dict(self.scan_kwargs)  # don't mutate original
        while True:
            response = table.scan(**kwargs)
            for item in response.get("Items", []):
                yield self.mapper(item)
            if "LastEvaluatedKey" not in response:
                break
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
