"""End-to-end integration test: DynamoDB -> Moss.

Reads from a pre-existing DynamoDB table (create it yourself or use
DynamoDB Local), ingests into a live Moss project via ``ingest()``,
runs a real semantic query, and cleans up the Moss index on exit.

SKIPPED unless DYNAMODB_TABLE, AWS_REGION, MOSS_PROJECT_ID, and
MOSS_PROJECT_KEY are all set.

Run with:
    pytest tests/test_integration_dynamodb_moss.py -v -s
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("boto3")

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for candidate in (
        _here.parents[1] / ".env",                              # this package's own .env
        _here.parents[2] / ".env",                              # shared creds at moss-data-connector/.env
        _here.parents[4] / ".env",                              # <repo>/.env
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)
except ImportError:
    pass

from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402

from moss_connector_dynamodb import DynamoDBConnector, ingest  # noqa: E402

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
AWS_REGION = os.getenv("AWS_REGION")
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL")  # optional, for DynamoDB Local

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (DYNAMODB_TABLE and AWS_REGION and PROJECT_ID and PROJECT_KEY),
    reason="Set DYNAMODB_TABLE, AWS_REGION, MOSS_PROJECT_ID, and MOSS_PROJECT_KEY to run.",
)


async def test_dynamodb_live_ingest_to_moss():
    """Full round trip: DynamoDB items -> ingest() -> Moss index -> query -> delete."""
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-connectors-dynamodb-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = DynamoDBConnector(
            table_name=DYNAMODB_TABLE,
            mapper=lambda item: DocumentInfo(
                id=str(item.get("id", item.get("pk", "unknown"))),
                text=str(item.get("text", item.get("body", item.get("content", "")))),
                metadata={
                    k: str(v) for k, v in item.items()
                    if k not in ("id", "pk", "text", "body", "content")
                },
            ),
            region_name=AWS_REGION,
            endpoint_url=DYNAMODB_ENDPOINT_URL,
        )

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None, "expected at least one item in the DynamoDB table"
        assert result.doc_count > 0

        await client.load_index(index_name)
        query_result = await client.query(
            index_name, "test query", QueryOptions(top_k=3)
        )
        assert query_result.docs, "expected at least one document in the search result"

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
