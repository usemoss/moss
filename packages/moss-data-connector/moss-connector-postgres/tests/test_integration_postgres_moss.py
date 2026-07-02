"""End-to-end integration test against a real PostgreSQL database and Moss project.

This test actually creates a temporary table in Postgres, ingests from it into a
real Moss index, queries the index, and cleans up afterwards. It is SKIPPED
unless POSTGRES_DSN, MOSS_PROJECT_ID, and MOSS_PROJECT_KEY are all set in the
environment (or in a .env file at the repo root or package root).

POSTGRES_DSN should be a connection string like:
    postgresql://user:password@host:port/database

Run it with:
    cd packages/moss-data-connector/moss-connector-postgres
    pytest tests/test_integration_postgres_moss.py -v -s
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

# Load .env from the package dir, then the repo root, if present.
try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for candidate in (
        _here.parents[1] / ".env",                   # this package's own .env
        _here.parents[2] / ".env",                   # moss-data-connector/.env
        _here.parents[4] / ".env",                   # <repo>/.env
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)
except ImportError:
    pass  # dotenv is optional; env vars can also be set directly.

pytest.importorskip("psycopg")

import psycopg  # noqa: E402
import psycopg.rows  # noqa: E402
from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402
from moss_connector_postgres import PostgresConnector, ingest  # noqa: E402

POSTGRES_DSN = os.getenv("POSTGRES_DSN")
PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (POSTGRES_DSN and PROJECT_ID and PROJECT_KEY),
    reason="Set POSTGRES_DSN, MOSS_PROJECT_ID, and MOSS_PROJECT_KEY to run the real integration test.",
)


@pytest.fixture()
def postgres_table():
    """Create a temporary table with 5 recognisable rows, drop it after the test."""
    table_name = f"moss_test_{uuid.uuid4().hex[:8]}"
    conn = psycopg.connect(POSTGRES_DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TEMPORARY TABLE {table_name} "
                "(id INT PRIMARY KEY, title VARCHAR(255), body TEXT)"
            )
            cur.executemany(
                f"INSERT INTO {table_name} (id, title, body) VALUES (%s, %s, %s)",
                [
                    (1, "Refund policy", "Refunds take 3 to 5 business days."),
                    (2, "Shipping time", "Orders ship within 24 hours."),
                    (3, "Contact support", "Reach support 24/7 via live chat."),
                    (4, "Password reset", "Click the link on the login page."),
                    (5, "Order tracking", "Tracking number sent by email."),
                ],
            )
        yield table_name
    finally:
        conn.close()


async def test_postgres_ingest_end_to_end(postgres_table):
    """Full round trip: Postgres → Moss index → query → delete."""
    table_name = postgres_table
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    # Unique index name per run so concurrent runs don't collide.
    index_name = f"moss-postgres-e2e-{uuid.uuid4().hex[:8]}"

    try:
        connector = PostgresConnector(
            dsn=POSTGRES_DSN,
            query=f"SELECT id, title, body FROM {table_name}",
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
        result = await client.query(
            index_name, "how long do refunds take", QueryOptions(top_k=3)
        )

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