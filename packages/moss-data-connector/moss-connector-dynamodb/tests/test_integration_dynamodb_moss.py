"""End-to-end integration test: DynamoDB → Moss.

Populates a temporary DynamoDB table (against real AWS or a local endpoint
such as DynamoDB Local / LocalStack), ingests it into a live Moss project via
``ingest()``, runs a real semantic query, and cleans everything up on exit.

SKIPPED unless both MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set.

Run with:
    pytest tests/test_integration_dynamodb_moss.py -v -s

Environment variables (set in .env or the shell):
    MOSS_PROJECT_ID      — required
    MOSS_PROJECT_KEY     — required
    AWS_ACCESS_KEY_ID    — required (or configure via ~/.aws/credentials)
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION   — defaults to us-east-1
    DYNAMODB_TABLE       — name of the test table to create (default: moss-connector-test)
    DYNAMODB_ENDPOINT_URL — optional; set to http://localhost:8000 for DynamoDB Local
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import boto3
import pytest
from dotenv import load_dotenv

from boto3.dynamodb.conditions import Attr, Key  # noqa: E402

from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402
from moss_connector_dynamodb import DynamoDBConnector, DynamoDBQueryConnector, ingest  # noqa: E402

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
TABLE_BASE = os.getenv("DYNAMODB_TABLE", "moss-connector-test")
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL")  # None → real AWS

pytestmark = pytest.mark.skipif(
    not (PROJECT_ID and PROJECT_KEY),
    reason="Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY to run this live test.",
)

ARTICLES = [
    {
        "sku": "ART-001",
        "headline": "Refund policy",
        "full_text": "Refunds are processed within 3 to 5 business days.",
        "category": "billing",
        "author": "ada",
        "word_count": Decimal("12"),
        "published": True,
    },
    {
        "sku": "ART-002",
        "headline": "Shipping time",
        "full_text": "Most orders ship within 24 hours of being placed.",
        "category": "shipping",
        "author": "bob",
        "word_count": Decimal("10"),
        "published": True,
    },
    {
        "sku": "ART-003",
        "headline": "Contact support",
        "full_text": "You can reach our support team 24/7 via live chat.",
        "category": "support",
        "author": "cal",
        "word_count": Decimal("11"),
        "published": True,
    },
    {
        "sku": "ART-004",
        "headline": "Password reset",
        "full_text": "To reset your password, click the link on the login page.",
        "category": "account",
        "author": "dee",
        "word_count": Decimal("12"),
        "published": True,
    },
    {
        "sku": "ART-005",
        "headline": "Order tracking",
        "full_text": "Every shipped order includes a tracking number by email.",
        "category": "shipping",
        "author": "eli",
        "word_count": Decimal("10"),
        "published": True,
    },
]


def _boto3_kwargs() -> dict:
    kw: dict = {"region_name": REGION}
    if ENDPOINT_URL:
        kw["endpoint_url"] = ENDPOINT_URL
    return kw


@pytest.fixture()
def dynamo_table():
    """Create a uniquely named DynamoDB table, populate it, drop it on exit."""
    table_name = f"{TABLE_BASE}-{uuid.uuid4().hex[:8]}"
    ddb = boto3.resource("dynamodb", **_boto3_kwargs())
    table = ddb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "sku", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "sku", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    for item in ARTICLES:
        table.put_item(Item=item)
    try:
        yield table_name
    finally:
        table.delete()


async def test_dynamodb_scan_live_ingest_to_moss(dynamo_table):
    """Full round trip: DynamoDB Scan → ingest() → Moss index → query → delete."""
    table_name = dynamo_table
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-connectors-dynamo-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = DynamoDBConnector(
            table_name=table_name,
            mapper=lambda item: DocumentInfo(
                id=item["sku"],
                text=item["full_text"],
                metadata={
                    "headline": item["headline"],
                    "category": item["category"],
                    "author": item["author"],
                    "word_count": str(item["word_count"]),
                    "published": str(item["published"]),
                },
            ),
            **_boto3_kwargs(),
        )

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count == 5

        await client.load_index(index_name)
        result = await client.query(
            index_name, "how long do refunds take", QueryOptions(top_k=3)
        )

        assert result.docs, "expected at least one document in the search result"
        top_ids = [d.id for d in result.docs]
        assert "ART-001" in top_ids, f"refund-policy doc not in top 3: {top_ids}"

        refund_doc = next(d for d in result.docs if d.id == "ART-001")
        assert refund_doc.metadata is not None
        assert refund_doc.metadata.get("headline") == "Refund policy"
        assert refund_doc.metadata.get("category") == "billing"
        assert refund_doc.metadata.get("word_count") == "12"
        assert refund_doc.metadata.get("published") == "True"

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")


async def test_dynamodb_filter_expression_live(dynamo_table):
    """Only 'billing' items should be ingested when a FilterExpression is applied."""
    table_name = dynamo_table
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-connectors-dynamo-filter-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = DynamoDBConnector(
            table_name=table_name,
            mapper=lambda item: DocumentInfo(
                id=item["sku"],
                text=item["full_text"],
                metadata={"category": item["category"]},
            ),
            filter_expression=Attr("category").eq("billing"),
            **_boto3_kwargs(),
        )

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count == 1

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
