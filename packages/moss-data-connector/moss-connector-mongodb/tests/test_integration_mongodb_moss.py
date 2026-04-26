"""End-to-end integration test: MongoDB -> Moss.

Populates a temporary database on a local MongoDB (URI hardcoded below),
ingests it into a live Moss project via `ingest()`, runs a real semantic
query, and cleans everything up on exit.

SKIPPED unless both MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set.

Run with:
    pytest tests/test_integration_mongodb_moss.py -v -s
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("pymongo")

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

from moss_connector_mongodb import MongoDBConnector, ingest  # noqa: E402

# Point this at whatever Mongo you're running locally.
MONGODB_URI = "mongodb://localhost:27017"

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (PROJECT_ID and PROJECT_KEY),
    reason="Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY to run this live test.",
)


@pytest.fixture()
def mongo_database():
    """Populate a unique DB with richly-typed articles; drop on exit.

    Field names deliberately avoid `id`, `text`, and `metadata` so the mapping
    is clearly translating source fields into Moss concepts.
    """
    from pymongo import MongoClient

    db_name = f"e2e_{uuid.uuid4().hex[:8]}"
    mongo = MongoClient(MONGODB_URI)
    try:
        mongo[db_name]["articles"].insert_many(
            [
                {
                    "sku": "ART-001",
                    "headline": "Refund policy",
                    "full_text": "Refunds are processed within 3 to 5 business days.",
                    "category": "billing",
                    "author": "ada",
                    "word_count": 12,
                    "published": True,
                },
                {
                    "sku": "ART-002",
                    "headline": "Shipping time",
                    "full_text": "Most orders ship within 24 hours of being placed.",
                    "category": "shipping",
                    "author": "bob",
                    "word_count": 10,
                    "published": True,
                },
                {
                    "sku": "ART-003",
                    "headline": "Contact support",
                    "full_text": "You can reach our support team 24/7 via live chat.",
                    "category": "support",
                    "author": "cal",
                    "word_count": 11,
                    "published": True,
                },
                {
                    "sku": "ART-004",
                    "headline": "Password reset",
                    "full_text": "To reset your password, click the link on the login page.",
                    "category": "account",
                    "author": "dee",
                    "word_count": 12,
                    "published": True,
                },
                {
                    "sku": "ART-005",
                    "headline": "Order tracking",
                    "full_text": "Every shipped order includes a tracking number by email.",
                    "category": "shipping",
                    "author": "eli",
                    "word_count": 10,
                    "published": True,
                },
            ]
        )
        yield db_name
    finally:
        mongo.drop_database(db_name)
        mongo.close()


async def test_mongodb_live_ingest_to_moss(mongo_database):
    """Full round trip: MongoDB docs -> ingest() -> Moss index -> query -> delete."""
    db_name = mongo_database
    # ingest() builds its own MossClient from the creds; we need one here too
    # for the query + cleanup assertions below.
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    index_name = f"moss-connectors-mongo-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = MongoDBConnector(
            uri=MONGODB_URI,
            database=db_name,
            collection="articles",
            mapper=lambda r: DocumentInfo(
                id=str(r["sku"]),
                text=r["full_text"],
                metadata={
                    "headline": r["headline"],
                    "category": r["category"],
                    "author": r["author"],
                    "word_count": str(r["word_count"]),
                    "published": str(r["published"]),
                },
            ),
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
        # String fields survive as-is; int/bool are coerced to str for Moss.
        assert refund_doc.metadata.get("headline") == "Refund policy"
        assert refund_doc.metadata.get("category") == "billing"
        assert refund_doc.metadata.get("author") == "ada"
        assert refund_doc.metadata.get("word_count") == "12"
        assert refund_doc.metadata.get("published") == "True"

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
