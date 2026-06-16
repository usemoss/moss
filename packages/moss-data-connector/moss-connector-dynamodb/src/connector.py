"""DynamoDB connector.

Reads items from a DynamoDB table via ``boto3`` and yields one
``DocumentInfo`` per item. Handles pagination automatically using
``LastEvaluatedKey``.

Two scan strategies are provided:

* **DynamoDBConnector** — full-table ``Scan``, optionally filtered with a
  boto3 ``FilterExpression`` and a ``ProjectionExpression``.
* **DynamoDBQueryConnector** — partition-key ``Query``, for when you want
  to ingest only items belonging to a specific partition.

Both connectors accept ``boto3.resource`` kwargs (``region_name``,
``endpoint_url``, ``aws_access_key_id``, etc.) passed through to the
DynamoDB resource so you can target LocalStack, DynamoDB Local, or a
specific AWS region without extra boilerplate.

Note on attribute types: DynamoDB returns Python-native types via
``boto3``'s high-level resource API (e.g. ``Decimal`` for numbers,
``bytes`` for Binary). Coerce non-string values to ``str`` in your
``mapper`` before assigning them to ``DocumentInfo.id`` or
``DocumentInfo.metadata``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import boto3
from boto3.dynamodb.conditions import ConditionBase
from moss import DocumentInfo


class DynamoDBConnector:
    """Scan a DynamoDB table and yield one ``DocumentInfo`` per item.

    By default performs a full-table ``Scan``. Pass ``filter_expression``
    (a boto3 ``ConditionBase``, e.g. ``Attr('status').eq('published')``) to
    restrict which items are returned. Pass ``projection_expression`` (a
    comma-separated string of attribute names, e.g. ``\"id, title, body\"``)
    to limit which attributes come back.

    All items are paged automatically via ``LastEvaluatedKey``; the caller
    sees a flat iterator regardless of how many pages DynamoDB returns.

    Args:
        table_name: Name of the DynamoDB table.
        mapper: Callable that turns an item (``dict[str, Any]``) into a
            ``DocumentInfo``.
        filter_expression: Optional boto3 condition to filter items server-side.
        projection_expression: Optional comma-separated attribute names.
        page_size: Number of items to request per ``Scan`` page (maps to
            ``Limit`` in the DynamoDB API). Defaults to 100.  Setting this
            lower reduces peak memory at the cost of more round trips.
        **boto3_kwargs: Extra keyword arguments forwarded to
            ``boto3.resource("dynamodb", ...)`` — e.g. ``region_name``,
            ``endpoint_url``, ``aws_access_key_id``, ``aws_secret_access_key``.
    """

    def __init__(
        self,
        table_name: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        filter_expression: ConditionBase | None = None,
        projection_expression: str | None = None,
        page_size: int = 100,
        **boto3_kwargs: Any,
    ) -> None:
        self.table_name = table_name
        self.mapper = mapper
        self.filter_expression = filter_expression
        self.projection_expression = projection_expression
        self.page_size = page_size
        self.boto3_kwargs = boto3_kwargs

    def __iter__(self) -> Iterator[DocumentInfo]:
        dynamodb = boto3.resource("dynamodb", **self.boto3_kwargs)
        table = dynamodb.Table(self.table_name)

        kwargs: dict[str, Any] = {"Limit": self.page_size}
        if self.filter_expression is not None:
            kwargs["FilterExpression"] = self.filter_expression
        if self.projection_expression is not None:
            kwargs["ProjectionExpression"] = self.projection_expression

        while True:
            response = table.scan(**kwargs)
            for item in response.get("Items", []):
                yield self.mapper(item)
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key


class DynamoDBQueryConnector:
    """Query a DynamoDB table by partition key and yield one ``DocumentInfo`` per item.

    Use this connector when you want to ingest only the items that belong to a
    specific partition key value. For a full-table ingest, prefer
    ``DynamoDBConnector`` (which uses ``Scan``).

    Args:
        table_name: Name of the DynamoDB table.
        key_condition_expression: A boto3 ``ConditionBase`` that identifies the
            partition (and optionally the sort-key range), e.g.
            ``Key('pk').eq('PRODUCT') & Key('sk').begins_with('v2#')``.
        mapper: Callable that turns an item (``dict[str, Any]``) into a
            ``DocumentInfo``.
        filter_expression: Optional boto3 condition applied *after* the key
            condition to filter items server-side.
        projection_expression: Optional comma-separated attribute names.
        index_name: Name of a Global or Local Secondary Index to query instead
            of the base table.
        page_size: Number of items to request per ``Query`` page.
        **boto3_kwargs: Forwarded to ``boto3.resource("dynamodb", ...)``.
    """

    def __init__(
        self,
        table_name: str,
        key_condition_expression: ConditionBase,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        filter_expression: ConditionBase | None = None,
        projection_expression: str | None = None,
        index_name: str | None = None,
        page_size: int = 100,
        **boto3_kwargs: Any,
    ) -> None:
        self.table_name = table_name
        self.key_condition_expression = key_condition_expression
        self.mapper = mapper
        self.filter_expression = filter_expression
        self.projection_expression = projection_expression
        self.index_name = index_name
        self.page_size = page_size
        self.boto3_kwargs = boto3_kwargs

    def __iter__(self) -> Iterator[DocumentInfo]:
        dynamodb = boto3.resource("dynamodb", **self.boto3_kwargs)
        table = dynamodb.Table(self.table_name)

        kwargs: dict[str, Any] = {
            "KeyConditionExpression": self.key_condition_expression,
            "Limit": self.page_size,
        }
        if self.filter_expression is not None:
            kwargs["FilterExpression"] = self.filter_expression
        if self.projection_expression is not None:
            kwargs["ProjectionExpression"] = self.projection_expression
        if self.index_name is not None:
            kwargs["IndexName"] = self.index_name

        while True:
            response = table.query(**kwargs)
            for item in response.get("Items", []):
                yield self.mapper(item)
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
