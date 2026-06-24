#!/usr/bin/env python3
"""
DynamoDB → Moss end-to-end demo script
=======================================
Reads creds from .env (repo root, package dir, or environment variables).

Steps:
  1. Create a DynamoDB table (Local or AWS)
  2. Insert sample product-support articles
  3. Scan the table → ingest into a Moss index
  4. Query the Moss index with a natural-language question
  5. Print the top results
  6. Clean up (delete Moss index + drop DynamoDB table)

Usage:
    python demo.py
    python demo.py --skip-cleanup   # leave the table + index around to inspect

Environment variables (loaded from .env automatically):
    AWS_ACCESS_KEY_ID          fakekey          (any string for DynamoDB Local)
    AWS_SECRET_ACCESS_KEY      fakesecret
    AWS_DEFAULT_REGION         us-east-1
    DYNAMODB_ENDPOINT_URL      http://localhost:8000
    MOSS_PROJECT_ID            your-project-id
    MOSS_PROJECT_KEY           your-project-key
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

# ── load .env (repo root → package dir, whichever exists) ──────────────────
try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for _candidate in (
        _here.parent / ".env",  # package dir
        _here.parents[3] / ".env",  # moss-data-connector/
        _here.parents[5] / ".env",  # repo root
    ):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass  # python-dotenv optional; rely on env vars set in the shell

import boto3
from moss import DocumentInfo, MossClient, QueryOptions
from moss_connector_dynamodb import DynamoDBConnector, ingest

# ── config ──────────────────────────────────────────────────────────────────
TABLE_NAME = f"moss-demo-{uuid.uuid4().hex[:6]}"
INDEX_NAME = f"moss-demo-{uuid.uuid4().hex[:6]}"
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
ENDPOINT_URL = os.getenv(
    "DYNAMODB_ENDPOINT_URL"
)  # None → real AWS (guarded by MOSS_CONNECTOR_DYNAMODB_ALLOW_AWS=1)
MOSS_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_KEY = os.getenv("MOSS_PROJECT_KEY")

SAMPLE_ARTICLES = [
    {
        "sku": "ART-001",
        "title": "Refund policy",
        "body": "Refunds are processed within 3 to 5 business days after approval.",
        "category": "billing",
        "author": "ada",
        "word_count": Decimal("14"),
    },
    {
        "sku": "ART-002",
        "title": "Shipping time",
        "body": "Most orders ship within 24 hours of being placed.",
        "category": "shipping",
        "author": "bob",
        "word_count": Decimal("10"),
    },
    {
        "sku": "ART-003",
        "title": "Contact support",
        "body": "You can reach our support team 24/7 via live chat or email.",
        "category": "support",
        "author": "cal",
        "word_count": Decimal("13"),
    },
    {
        "sku": "ART-004",
        "title": "Password reset",
        "body": "To reset your password, click the link on the login page.",
        "category": "account",
        "author": "dee",
        "word_count": Decimal("12"),
    },
    {
        "sku": "ART-005",
        "title": "Order tracking",
        "body": "Every shipped order includes a tracking number sent by email.",
        "category": "shipping",
        "author": "eli",
        "word_count": Decimal("11"),
    },
    {
        "sku": "ART-006",
        "title": "Return window",
        "body": "Items can be returned within 30 days of delivery for a full refund.",
        "category": "billing",
        "author": "ada",
        "word_count": Decimal("14"),
    },
    {
        "sku": "ART-007",
        "title": "Express shipping",
        "body": "Express delivery is available for an additional fee and arrives in 1-2 days.",
        "category": "shipping",
        "author": "bob",
        "word_count": Decimal("14"),
    },
]

QUERIES = [
    "how long do refunds take",
    "can I track my order",
    "how do I reset my password",
    "overnight delivery options",
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


# ── step 1: create DynamoDB table ──────────────────────────────────────────
def create_table():
    sep("Step 1 — Create DynamoDB table")
    ddb = boto3.resource("dynamodb", **boto3_kwargs())
    table = ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[{"AttributeName": "sku", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "sku", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    print(f"  ✓ Table '{TABLE_NAME}' created")
    return table


# ── step 2: insert sample items ─────────────────────────────────────────────
def insert_items(table) -> None:
    sep("Step 2 — Insert sample articles")
    with table.batch_writer() as batch:
        for item in SAMPLE_ARTICLES:
            batch.put_item(Item=item)
    print(f"  ✓ Inserted {len(SAMPLE_ARTICLES)} articles")
    for item in SAMPLE_ARTICLES:
        print(f"      [{item['sku']}] {item['title']} ({item['category']})")


# ── step 3: ingest into Moss ─────────────────────────────────────────────────
async def ingest_to_moss() -> None:
    sep("Step 3 — Ingest DynamoDB → Moss")
    source = DynamoDBConnector(
        table_name=TABLE_NAME,
        mapper=lambda item: DocumentInfo(
            id=item["sku"],
            text=item["body"],
            metadata={
                "title": item["title"],
                "category": item["category"],
                "author": item["author"],
                "word_count": str(item["word_count"]),
            },
        ),
        **boto3_kwargs(),
    )

    result = await ingest(source, MOSS_ID, MOSS_KEY, index_name=INDEX_NAME)
    if result is None:
        print("  ✗ No documents were ingested (empty table?)")
        sys.exit(1)
    print(f"  ✓ Ingested {result.doc_count} documents into Moss index '{INDEX_NAME}'")


# ── step 4: query Moss ───────────────────────────────────────────────────────
async def query_moss() -> None:
    sep("Step 4 — Semantic queries")
    client = MossClient(MOSS_ID, MOSS_KEY)
    await client.load_index(INDEX_NAME)

    for question in QUERIES:
        result = await client.query(INDEX_NAME, question, QueryOptions(top_k=3))
        print(f'\n  Query: "{question}"')
        if not result.docs:
            print("    (no results)")
            continue
        for rank, doc in enumerate(result.docs, 1):
            title = (doc.metadata or {}).get("title", "?")
            cat = (doc.metadata or {}).get("category", "?")
            print(f"    #{rank}  [{doc.id}] {title}  ({cat})")
            print(f"         {doc.text[:80]}{'…' if len(doc.text) > 80 else ''}")


# ── step 5: cleanup ──────────────────────────────────────────────────────────
async def cleanup() -> None:
    sep("Step 5 — Cleanup")
    # delete Moss index
    try:
        client = MossClient(MOSS_ID, MOSS_KEY)
        await client.delete_index(INDEX_NAME)
        print(f"  ✓ Moss index '{INDEX_NAME}' deleted")
    except Exception as exc:
        print(f"  ⚠ Could not delete Moss index: {exc}")

    # drop DynamoDB table
    try:
        ddb = boto3.resource("dynamodb", **boto3_kwargs())
        table = ddb.Table(TABLE_NAME)
        table.delete()
        table.wait_until_not_exists()
        print(f"  ✓ DynamoDB table '{TABLE_NAME}' deleted")
    except Exception as exc:
        print(f"  ⚠ Could not delete DynamoDB table: {exc}")


# ── main ─────────────────────────────────────────────────────────────────────
async def main(skip_cleanup: bool) -> None:
    # Validate env
    missing = [v for v in ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY") if not os.getenv(v)]
    if missing:
        print(f"Error: missing environment variables: {', '.join(missing)}")
        print("Copy .env.example → .env and fill in your credentials.")
        sys.exit(1)

    if not ENDPOINT_URL and os.getenv("MOSS_CONNECTOR_DYNAMODB_ALLOW_AWS") != "1":
        print("Error: DYNAMODB_ENDPOINT_URL is not set.")
        print("This demo targets DynamoDB Local by default.")
        print("To run against real AWS, set MOSS_CONNECTOR_DYNAMODB_ALLOW_AWS=1.")
        sys.exit(1)

    mode = f"DynamoDB Local ({ENDPOINT_URL})" if ENDPOINT_URL else f"AWS {REGION}"
    sep()
    print("  DynamoDB → Moss  demo")
    print(f"  DynamoDB : {mode}")
    print(f"  Table    : {TABLE_NAME}")
    print(f"  Index    : {INDEX_NAME}")
    sep()

    table = create_table()
    insert_items(table)
    await ingest_to_moss()
    await query_moss()

    if skip_cleanup:
        sep()
        print(f"  --skip-cleanup set. Table '{TABLE_NAME}' and index '{INDEX_NAME}' left in place.")
    else:
        await cleanup()

    sep()
    print("  Done!")
    sep()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DynamoDB → Moss demo")
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Leave the DynamoDB table and Moss index in place after the demo.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.skip_cleanup))
