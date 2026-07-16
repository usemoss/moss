"""End-to-end integration test: S3 → Moss.

Populates a temporary S3 bucket (against real AWS or a local endpoint such
as MinIO / LocalStack), ingests it into a live Moss project via ``ingest()``,
runs a real semantic query, exercises ``watch()`` re-indexing, and cleans
everything up on exit.

SKIPPED unless both MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set.
SKIPPED unless S3_ENDPOINT_URL is set (local endpoint) or
    MOSS_CONNECTOR_S3_ALLOW_AWS=1 explicitly opts in to real AWS.

Run with:
    pytest tests/test_integration_s3_moss.py -v -s

Environment variables (set in .env or the shell):
    MOSS_PROJECT_ID              — required
    MOSS_PROJECT_KEY             — required
    AWS_ACCESS_KEY_ID            — required (or configure via ~/.aws/credentials)
    AWS_SECRET_ACCESS_KEY
    AWS_DEFAULT_REGION           — defaults to us-east-1
    S3_BUCKET                    — base name of the test bucket to create (default: moss-connector-test)
    S3_ENDPOINT_URL              — set to http://localhost:9000 for MinIO / http://localhost:4566 for LocalStack
    MOSS_CONNECTOR_S3_ALLOW_AWS  — set to 1 to run against real AWS instead
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import boto3
import pytest

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for _candidate in (
        _here.parents[1] / ".env",  # this package's own .env
        _here.parents[2] / ".env",  # shared creds at moss-data-connector/.env
        _here.parents[4] / ".env",  # <repo>/.env
    ):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass

from moss import DocumentInfo, MossClient, QueryOptions
from moss_connector_s3 import S3Connector, ingest, watch

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BUCKET_BASE = os.getenv("S3_BUCKET", "moss-connector-test")
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # None → real AWS
_ALLOW_AWS = os.getenv("MOSS_CONNECTOR_S3_ALLOW_AWS") == "1"

pytestmark = [
    pytest.mark.skipif(
        not (PROJECT_ID and PROJECT_KEY),
        reason="Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY to run this live test.",
    ),
    pytest.mark.skipif(
        not (ENDPOINT_URL or _ALLOW_AWS),
        reason=(
            "Set S3_ENDPOINT_URL (e.g. http://localhost:9000) for MinIO / LocalStack, "
            "or set MOSS_CONNECTOR_S3_ALLOW_AWS=1 to run against real AWS."
        ),
    ),
]

ARTICLES = {
    "kb/refunds.md": {
        "body": "Refunds are processed within 3 to 5 business days.",
        "category": "billing",
    },
    "kb/shipping.md": {
        "body": "Most orders ship within 24 hours of being placed.",
        "category": "shipping",
    },
    "kb/support.md": {
        "body": "You can reach our support team 24/7 via live chat.",
        "category": "support",
    },
    "kb/password-reset.md": {
        "body": "To reset your password, click the link on the login page.",
        "category": "account",
    },
    "kb/order-tracking.md": {
        "body": "Every shipped order includes a tracking number sent by email.",
        "category": "shipping",
    },
}


def _boto3_kwargs() -> dict:
    kw: dict = {"region_name": REGION}
    if ENDPOINT_URL:
        kw["endpoint_url"] = ENDPOINT_URL
    return kw


def _create_bucket(s3, name: str) -> None:
    if REGION == "us-east-1":
        s3.create_bucket(Bucket=name)
    else:
        s3.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": REGION})


@pytest.fixture()
def s3_bucket():
    """Create a uniquely named bucket, populate it, empty and delete it on exit."""
    bucket_name = f"{BUCKET_BASE}-{uuid.uuid4().hex[:8]}"
    s3 = boto3.client("s3", **_boto3_kwargs())
    _create_bucket(s3, bucket_name)
    for key, article in ARTICLES.items():
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=article["body"].encode("utf-8"),
            ContentType="text/markdown",
            Metadata={"category": article["category"]},
        )
    try:
        yield bucket_name
    finally:
        listed = s3.list_objects_v2(Bucket=bucket_name)
        for obj in listed.get("Contents", []):
            s3.delete_object(Bucket=bucket_name, Key=obj["Key"])
        s3.delete_bucket(Bucket=bucket_name)


def _mapper(row: dict) -> DocumentInfo:
    return DocumentInfo(
        id=row["key"],
        text=row["text"],
        metadata={
            "category": row["metadata"].get("category", ""),
            "etag": row["etag"],
        },
    )


async def test_s3_live_ingest_to_moss(s3_bucket):
    """Full round trip: S3 list/get → ingest() → Moss index → query → delete."""
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-connectors-s3-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = S3Connector(bucket=s3_bucket, mapper=_mapper, prefix="kb/", **_boto3_kwargs())

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count == 5

        await client.load_index(index_name)
        result = await client.query(index_name, "how long do refunds take", QueryOptions(top_k=3))

        assert result.docs, "expected at least one document in the search result"
        top_ids = [d.id for d in result.docs]
        assert "kb/refunds.md" in top_ids, f"refund-policy doc not in top 3: {top_ids}"

        refund_doc = next(d for d in result.docs if d.id == "kb/refunds.md")
        assert refund_doc.metadata is not None
        assert refund_doc.metadata.get("category") == "billing"

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")


async def test_s3_watch_reindexes_live(s3_bucket):
    """watch() picks up a new object and rebuilds the live index."""
    import asyncio

    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-connectors-s3-watch-{uuid.uuid4().hex[:8]}"
    s3 = boto3.client("s3", **_boto3_kwargs())

    try:
        source = S3Connector(bucket=s3_bucket, mapper=_mapper, prefix="kb/", **_boto3_kwargs())

        async def add_object_soon():
            # Land the new object while watch() is between polls.
            await asyncio.sleep(0.5)
            s3.put_object(
                Bucket=s3_bucket,
                Key="kb/warranty.md",
                Body=b"All devices include a two year limited warranty.",
                ContentType="text/markdown",
                Metadata={"category": "billing"},
            )

        watch_task = watch(
            source, PROJECT_ID, PROJECT_KEY, index_name, poll_interval=1.0, max_polls=5
        )
        reindexed, _ = await asyncio.gather(watch_task, add_object_soon())

        # If the put landed before watch()'s initial snapshot, the first
        # ingest already covers it (reindexed == 0); otherwise a poll caught
        # it (reindexed >= 1). Either way the doc must be queryable.
        assert reindexed >= 0

        await client.load_index(index_name)
        result = await client.query(index_name, "is there a warranty", QueryOptions(top_k=3))
        assert "kb/warranty.md" in [d.id for d in result.docs]

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
