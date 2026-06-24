"""Unit tests for the DynamoDB connector.

No live AWS needed — we mock DynamoDB with ``moto`` so the test runs
anywhere ``boto3`` and ``moto[dynamodb]`` are importable, and we patch
``moss.MossClient`` inside ingest so no Moss network call is made.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import boto3
import pytest

pytest.importorskip("moto")

from moss import DocumentInfo  # noqa: E402
from moss_connector_dynamodb import DynamoDBConnector, DynamoDBQueryConnector, ingest  # noqa: E402
from moto import mock_aws  # noqa: E402

# ---------------------------------------------------------------------------
# Fake Moss client
# ---------------------------------------------------------------------------

TABLE_NAME = "articles"
REGION = "us-east-1"


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ITEMS = [
    {
        "sku": "ART-001",
        "headline": "Refund policy",
        "full_text": "Refunds are processed within 3 to 5 business days.",
        "category": "billing",
        "word_count": Decimal("12"),
    },
    {
        "sku": "ART-002",
        "headline": "Shipping time",
        "full_text": "Most orders ship within 24 hours of being placed.",
        "category": "shipping",
        "word_count": Decimal("10"),
    },
    {
        "sku": "ART-003",
        "headline": "Contact support",
        "full_text": "You can reach our support team 24/7 via live chat.",
        "category": "support",
        "word_count": Decimal("11"),
    },
]


@pytest.fixture()
def ddb_table():
    """Spin up a moto-mocked DynamoDB table and populate it with SAMPLE_ITEMS."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        table = ddb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "sku", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "sku", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        for item in SAMPLE_ITEMS:
            table.put_item(Item=item)
        yield table


def _simple_mapper(item: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=item["sku"],
        text=item["full_text"],
        metadata={
            "headline": item["headline"],
            "category": item["category"],
            "word_count": str(item["word_count"]),
        },
    )


# ---------------------------------------------------------------------------
# DynamoDBConnector (Scan) tests
# ---------------------------------------------------------------------------


async def test_scan_ingest_end_to_end(ddb_table):
    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name=TABLE_NAME,
            mapper=_simple_mapper,
            region_name=REGION,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 3

    docs = fake_moss.calls[0]["docs"]
    skus = {d.id for d in docs}
    assert skus == {"ART-001", "ART-002", "ART-003"}

    refund = next(d for d in docs if d.id == "ART-001")
    assert refund.text == "Refunds are processed within 3 to 5 business days."
    assert refund.metadata == {
        "headline": "Refund policy",
        "category": "billing",
        "word_count": "12",
    }


async def test_scan_auto_id_defaults_to_false(ddb_table):
    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name=TABLE_NAME,
            mapper=_simple_mapper,
            region_name=REGION,
        )
        await ingest(source, "fake_id", "fake_key", index_name="articles")

    docs = fake_moss.calls[0]["docs"]
    ids = {d.id for d in docs}
    assert ids == {"ART-001", "ART-002", "ART-003"}


async def test_scan_auto_id_replaces_mapper_id(ddb_table):
    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name=TABLE_NAME,
            mapper=_simple_mapper,
            region_name=REGION,
        )
        await ingest(source, "fake_id", "fake_key", index_name="articles", auto_id=True)

    docs = fake_moss.calls[0]["docs"]
    assert len(docs) == 3
    original_ids = {"ART-001", "ART-002", "ART-003"}
    for doc in docs:
        assert doc.id
        assert uuid.UUID(doc.id)  # valid UUID4
        assert doc.id not in original_ids


async def test_scan_filter_expression(ddb_table):
    """Only 'billing' items should be yielded when a FilterExpression is set."""
    from boto3.dynamodb.conditions import Attr

    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name=TABLE_NAME,
            mapper=_simple_mapper,
            filter_expression=Attr("category").eq("billing"),
            region_name=REGION,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="billing")

    assert result is not None
    assert result.doc_count == 1
    assert fake_moss.calls[0]["docs"][0].id == "ART-001"


async def test_scan_pagination(ddb_table):
    """page_size=1 forces multiple Scan pages; all items still arrive."""
    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBConnector(
            table_name=TABLE_NAME,
            mapper=_simple_mapper,
            page_size=1,
            region_name=REGION,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 3


async def test_scan_empty_table():
    """ingest() returns None when the table is empty."""
    fake_moss = FakeMossClient()

    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        table = ddb.create_table(
            TableName="empty",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()

        with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
            source = DynamoDBConnector(
                table_name="empty",
                mapper=lambda item: DocumentInfo(id=item["pk"], text=""),
                region_name=REGION,
            )
            result = await ingest(source, "fake_id", "fake_key", index_name="empty")

    assert result is None
    assert fake_moss.calls == []


# ---------------------------------------------------------------------------
# DynamoDBQueryConnector tests
# ---------------------------------------------------------------------------

QUERY_TABLE = "events"


@pytest.fixture()
def ddb_query_table():
    """Table keyed on (tenant_id [PK], event_id [SK]) with sample events."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        table = ddb.create_table(
            TableName=QUERY_TABLE,
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "event_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "event_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        rows = [
            {"tenant_id": "tenant-A", "event_id": "ev-1", "body": "First event for A"},
            {"tenant_id": "tenant-A", "event_id": "ev-2", "body": "Second event for A"},
            {"tenant_id": "tenant-B", "event_id": "ev-1", "body": "First event for B"},
        ]
        for row in rows:
            table.put_item(Item=row)
        yield table


async def test_query_connector_returns_only_matching_partition(ddb_query_table):
    from boto3.dynamodb.conditions import Key

    fake_moss = FakeMossClient()

    with patch("moss_connector_dynamodb.ingest.MossClient", return_value=fake_moss):
        source = DynamoDBQueryConnector(
            table_name=QUERY_TABLE,
            key_condition_expression=Key("tenant_id").eq("tenant-A"),
            mapper=lambda item: DocumentInfo(
                id=item["event_id"],
                text=item["body"],
                metadata={"tenant_id": item["tenant_id"]},
            ),
            region_name=REGION,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="events-A")

    assert result is not None
    assert result.doc_count == 2
    docs = fake_moss.calls[0]["docs"]
    assert {d.id for d in docs} == {"ev-1", "ev-2"}
    assert all(d.metadata["tenant_id"] == "tenant-A" for d in docs)
