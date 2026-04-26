"""End-to-end integration test against a real Moss project.

This test actually creates an index on Moss, ingests from a local SQLite DB,
queries it, and deletes the index afterwards. It is SKIPPED unless both
MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set in the environment (or in a
.env file at the repo root or package root).

Run it with:
    cd packages/moss-connectors
    pytest tests/test_integration_moss.py -v -s

Or filter to just this file:
    pytest -k integration_moss -v
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

import pytest

# Load .env from the package dir, then the repo root, if present.
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
    pass  # dotenv is optional; env vars can also be set directly.

from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402

from moss_connector_sqlite import SQLiteConnector, ingest  # noqa: E402

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (PROJECT_ID and PROJECT_KEY),
    reason="Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY to run the real integration test.",
)


@pytest.fixture()
def sqlite_source(tmp_path):
    """A 5-row SQLite DB with recognisable, query-friendly content."""
    path = tmp_path / "articles.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT, body TEXT)")
    conn.executemany(
        "INSERT INTO articles (id, title, body) VALUES (?, ?, ?)",
        [
            (1, "Refund policy", "Refunds are processed within 3 to 5 business days."),
            (2, "Shipping time", "Most orders ship within 24 hours of being placed."),
            (3, "Contact support", "You can reach our support team 24/7 via live chat."),
            (4, "Password reset", "To reset your password, click the link on the login page."),
            (5, "Order tracking", "Every shipped order includes a tracking number by email."),
        ],
    )
    conn.commit()
    conn.close()
    return str(path)


async def test_sqlite_ingest_end_to_end(sqlite_source):
    """Full round trip: SQLite -> Moss index -> query -> delete."""
    # ingest() builds its own MossClient from the creds; we need one here too
    # for the query + cleanup assertions below.
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    # Unique index name per run so concurrent runs don't collide.
    index_name = f"moss-connectors-e2e-{uuid.uuid4().hex[:8]}"

    try:
        connector = SQLiteConnector(
            database=sqlite_source,
            query="SELECT id, title, body FROM articles",
            mapper=lambda r: DocumentInfo(
                id=str(r["id"]),
                text=r["body"],
                metadata={"title": r["title"]},
            ),
        )

        result = await ingest(connector, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count == 5

        # Query the live index. "refund" should pull back article 1.
        await client.load_index(index_name)
        result = await client.query(index_name, "how long do refunds take", QueryOptions(top_k=3))

        assert result.docs, "expected at least one document in the search result"
        top_ids = [d.id for d in result.docs]
        assert "1" in top_ids, f"refund-policy doc not in top 3: {top_ids}"

        # Check the metadata survived the round trip.
        refund_doc = next(d for d in result.docs if d.id == "1")
        assert refund_doc.metadata is not None
        assert refund_doc.metadata.get("title") == "Refund policy"

    finally:
        # Always try to clean up, even if an assertion above failed.
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
