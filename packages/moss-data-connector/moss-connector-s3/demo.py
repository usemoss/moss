#!/usr/bin/env python3
"""
S3 → Moss end-to-end demo script
================================
Reads creds from .env (repo root, package dir, or environment variables).

Steps:
  1. Create an S3 bucket (MinIO / LocalStack or AWS)
  2. Upload sample product-support articles as objects
  3. List the bucket → ingest into a Moss index
  4. Query the Moss index with a natural-language question
  5. Upload a new object and re-ingest via one watch() poll
  6. Clean up (delete Moss index + empty and delete the bucket)

Usage:
    python demo.py
    python demo.py --skip-cleanup   # leave the bucket + index around to inspect

Environment variables (loaded from .env automatically):
    AWS_ACCESS_KEY_ID          minioadmin       (any string for MinIO/LocalStack)
    AWS_SECRET_ACCESS_KEY      minioadmin
    AWS_DEFAULT_REGION         us-east-1
    S3_ENDPOINT_URL            http://localhost:9000
    MOSS_PROJECT_ID            your-project-id
    MOSS_PROJECT_KEY           your-project-key
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

# ── load .env (repo root → package dir, whichever exists) ──────────────────
try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    # parents[1] → moss-data-connector/, parents[3] → repo root; guard the
    # depth so a shallow checkout of just this package can't IndexError.
    for _depth in (0, 1, 3):
        if _depth >= len(_here.parents):
            break
        _candidate = _here.parents[_depth] / ".env"
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass  # python-dotenv optional; rely on env vars set in the shell

import boto3
from moss import DocumentInfo, MossClient, QueryOptions
from moss_connector_s3 import S3Connector, ingest, watch

# ── config ──────────────────────────────────────────────────────────────────
BUCKET_NAME = f"moss-demo-{uuid.uuid4().hex[:6]}"
INDEX_NAME = f"moss-demo-{uuid.uuid4().hex[:6]}"
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # None → real AWS
MOSS_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_KEY = os.getenv("MOSS_PROJECT_KEY")

SAMPLE_ARTICLES = {
    "kb/refund-policy.md": {
        "body": "Refunds are processed within 3 to 5 business days after approval.",
        "category": "billing",
    },
    "kb/shipping-time.md": {
        "body": "Most orders ship within 24 hours of being placed.",
        "category": "shipping",
    },
    "kb/contact-support.md": {
        "body": "You can reach our support team 24/7 via live chat or email.",
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
    "kb/return-window.md": {
        "body": "Items can be returned within 30 days of delivery for a full refund.",
        "category": "billing",
    },
}

QUERIES = [
    "how long do refunds take",
    "can I track my order",
    "how do I reset my password",
]


def sep(title: str = "") -> None:
    width = 60
    if title:
        print(f"\n{'─' * 3} {title} {'─' * (width - len(title) - 5)}")
    else:
        print("─" * width)


def boto3_kwargs() -> dict:
    kw: dict = {"region_name": REGION}
    if ENDPOINT_URL:
        kw["endpoint_url"] = ENDPOINT_URL
    return kw


def make_source() -> S3Connector:
    return S3Connector(
        bucket=BUCKET_NAME,
        prefix="kb/",
        suffix=".md",
        mapper=lambda row: DocumentInfo(
            id=row["key"],
            text=row["text"],
            metadata={
                "category": row["metadata"].get("category", ""),
                "size": str(row["size"]),
            },
        ),
        **boto3_kwargs(),
    )


# ── step 1: create bucket ───────────────────────────────────────────────────
def create_bucket():
    sep("Step 1 — Create S3 bucket")
    s3 = boto3.client("s3", **boto3_kwargs())
    if REGION == "us-east-1":
        s3.create_bucket(Bucket=BUCKET_NAME)
    else:
        s3.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
    print(f"  ✓ Bucket '{BUCKET_NAME}' created")
    return s3


# ── step 2: upload sample objects ───────────────────────────────────────────
def upload_objects(s3) -> None:
    sep("Step 2 — Upload sample articles")
    for key, article in SAMPLE_ARTICLES.items():
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=article["body"].encode("utf-8"),
            ContentType="text/markdown",
            Metadata={"category": article["category"]},
        )
    print(f"  ✓ Uploaded {len(SAMPLE_ARTICLES)} articles")
    for key, article in SAMPLE_ARTICLES.items():
        print(f"      [{key}] ({article['category']})")


# ── step 3: ingest into Moss ─────────────────────────────────────────────────
async def ingest_to_moss() -> None:
    sep("Step 3 — Ingest S3 → Moss")
    result = await ingest(make_source(), MOSS_ID, MOSS_KEY, index_name=INDEX_NAME)
    if result is None:
        print("  ✗ No documents were ingested (empty bucket?)")
        sys.exit(1)
    print(f"  ✓ Ingested {result.doc_count} documents into Moss index '{INDEX_NAME}'")


# ── step 4: query ────────────────────────────────────────────────────────────
async def run_queries(client: MossClient) -> None:
    sep("Step 4 — Query the index")
    await client.load_index(INDEX_NAME)
    for q in QUERIES:
        result = await client.query(INDEX_NAME, q, QueryOptions(top_k=2))
        print(f'  "{q}"')
        for doc in result.docs:
            print(f"      → [{doc.id}] {doc.text}")


# ── step 5: change the bucket, watch() re-indexes ───────────────────────────
async def watch_once(s3) -> None:
    sep("Step 5 — Add an object, watch() re-indexes")

    async def add_soon():
        await asyncio.sleep(0.5)
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key="kb/warranty.md",
            Body=b"All devices include a two year limited warranty.",
            ContentType="text/markdown",
            Metadata={"category": "billing"},
        )
        print("  ✓ Uploaded kb/warranty.md while watching")

    reindexed, _ = await asyncio.gather(
        watch(make_source(), MOSS_ID, MOSS_KEY, INDEX_NAME, poll_interval=1.0, max_polls=5),
        add_soon(),
    )
    print(f"  ✓ watch() performed {reindexed} re-index(es)")


# ── step 6: cleanup ──────────────────────────────────────────────────────────
async def cleanup(s3, client: MossClient) -> None:
    sep("Step 6 — Clean up")
    try:
        await client.delete_index(INDEX_NAME)
        print(f"  ✓ Deleted Moss index '{INDEX_NAME}'")
    except Exception as exc:
        print(f"  ✗ Failed to delete index: {exc}")
    listed = s3.list_objects_v2(Bucket=BUCKET_NAME)
    for obj in listed.get("Contents", []):
        s3.delete_object(Bucket=BUCKET_NAME, Key=obj["Key"])
    s3.delete_bucket(Bucket=BUCKET_NAME)
    print(f"  ✓ Deleted bucket '{BUCKET_NAME}'")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-cleanup", action="store_true")
    args = parser.parse_args()

    if not (MOSS_ID and MOSS_KEY):
        print("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY (in .env or the shell).")
        sys.exit(1)
    if not ENDPOINT_URL and os.getenv("MOSS_CONNECTOR_S3_ALLOW_AWS") != "1":
        print(
            "Set S3_ENDPOINT_URL (e.g. http://localhost:9000 for MinIO), or set\n"
            "MOSS_CONNECTOR_S3_ALLOW_AWS=1 to run against real AWS."
        )
        sys.exit(1)

    s3 = create_bucket()
    client = MossClient(MOSS_ID, MOSS_KEY)
    try:
        upload_objects(s3)
        await ingest_to_moss()
        await run_queries(client)
        await watch_once(s3)
    finally:
        if args.skip_cleanup:
            sep()
            print(f"Skipping cleanup: bucket '{BUCKET_NAME}', index '{INDEX_NAME}' left in place")
        else:
            await cleanup(s3, client)

    sep()
    print("Demo complete.")


if __name__ == "__main__":
    asyncio.run(main())
