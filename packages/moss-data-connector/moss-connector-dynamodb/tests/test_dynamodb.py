"""Unit tests for the DynamoDB connector. No live AWS needed, we mock
``boto3.resource`` so the test runs anywhere boto3 is importable, and
we patch ``moss.MossClient`` inside ingest so no Moss network call is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("boto3")

from moss import DocumentInfo  # noqa: E402

from moss_connector_dynamodb import DynamoDBConnector, ingest  # noqa: E402


@dataclass
class FakeMutationResult:
    doc_count: int
    job_id: str = "fake-job-id"
    index_name: str = ""


@dataclass
class FakeMossClient:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        docs = list(docs)
        self.calls.append({"name": name, "docs": docs, "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)


def _dynamo_mock_returning(pages: list[dict[str, Any]]) -> tuple[MagicMock, MagicMock]:
    """Build a mock ``boto3.resource("dynamodb")`` that returns paginated scan results.

    ``pages`` is a list of scan response dicts. Each must have ``"Items"`` and
    optionally ``"LastEvaluatedKey"``.

    Returns (resource, table) so the test can assert on either one.
    """
    table = MagicMock()
    table.scan.side_effect = pages
    resource = MagicMock()
    resource.Table.return_value = table
    return resource, table


def _simple_mapper(item: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=str(item["id"]),
        text=item["body"],
        metadata={"title": item["title"]},
    )


async def test_dynamodb_ingest_single_page():
    pages = [
        {
            "Items": [
                {"id": "a1", "title": "Refund policy", "body": "Refunds take 3-5 days."},
                {"id": "a2", "title": "Shipping", "body": "We ship within 24 hours."},
            ],
        },
    ]
    fake_resource, fake_table = _dynamo_mock_returning(pages)
    fake_moss = FakeMossClient()

    with patch(
        "moss_connector_dynamodb.connector.boto3.resource", return_value=fake_resource
    ), patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name="articles",
            mapper=_simple_mapper,
            region_name="us-east-1",
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 2
    fake_table.scan.assert_called_once_with()

    moss_docs = fake_moss.calls[0]["docs"]
    assert moss_docs[0].id == "a1"
    assert moss_docs[0].text == "Refunds take 3-5 days."
    assert moss_docs[0].metadata == {"title": "Refund policy"}


async def test_dynamodb_ingest_multi_page():
    pages = [
        {
            "Items": [
                {"id": "a1", "title": "Page one", "body": "First page content."},
            ],
            "LastEvaluatedKey": {"id": "a1"},
        },
        {
            "Items": [
                {"id": "a2", "title": "Page two", "body": "Second page content."},
            ],
        },
    ]
    fake_resource, fake_table = _dynamo_mock_returning(pages)
    fake_moss = FakeMossClient()

    with patch(
        "moss_connector_dynamodb.connector.boto3.resource", return_value=fake_resource
    ), patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name="articles",
            mapper=_simple_mapper,
            region_name="us-east-1",
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 2

    # Second call should include ExclusiveStartKey from first page
    calls = fake_table.scan.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs == {}
    assert calls[1].kwargs == {"ExclusiveStartKey": {"id": "a1"}}

    moss_docs = fake_moss.calls[0]["docs"]
    assert moss_docs[0].id == "a1"
    assert moss_docs[1].id == "a2"


async def test_dynamodb_forwards_scan_kwargs():
    pages = [{"Items": []}]
    fake_resource, fake_table = _dynamo_mock_returning(pages)
    fake_moss = FakeMossClient()

    my_scan_kwargs = {
        "FilterExpression": "category = :cat",
        "ProjectionExpression": "id, title, body",
        "ExpressionAttributeValues": {":cat": "billing"},
    }

    with patch(
        "moss_connector_dynamodb.connector.boto3.resource", return_value=fake_resource
    ), patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name="articles",
            mapper=_simple_mapper,
            region_name="us-east-1",
            scan_kwargs=my_scan_kwargs,
        )
        await ingest(source, "fake_id", "fake_key", index_name="x")

    fake_table.scan.assert_called_once_with(**my_scan_kwargs)


async def test_dynamodb_empty_table():
    pages = [{"Items": []}]
    fake_resource, _ = _dynamo_mock_returning(pages)
    fake_moss = FakeMossClient()

    with patch(
        "moss_connector_dynamodb.connector.boto3.resource", return_value=fake_resource
    ), patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name="empty",
            mapper=_simple_mapper,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="empty")

    assert result is None
    assert len(fake_moss.calls) == 0
