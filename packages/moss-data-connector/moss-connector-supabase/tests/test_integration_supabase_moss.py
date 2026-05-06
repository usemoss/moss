from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("supabase")

from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402
from moss_connector_supabase import SupabaseConnector, ingest  # noqa: E402
from supabase import create_client  # noqa: E402

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for candidate in (
        _here.parents[1] / ".env",
        _here.parents[2] / ".env",
        _here.parents[4] / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
PRESET_TABLE = os.getenv("SUPABASE_TEST_TABLE")

pytestmark = pytest.mark.skipif(
    not (SUPABASE_URL and SUPABASE_KEY and PROJECT_ID and PROJECT_KEY),
    reason="Set SUPABASE_URL, SUPABASE_KEY, MOSS_PROJECT_ID, MOSS_PROJECT_KEY to run.",
)


_SEED_ROWS = [
    {"id": 1, "title": "Refund policy", "body": "Refunds take 3 to 5 business days."},
    {"id": 2, "title": "Shipping time", "body": "Orders ship within 24 hours."},
    {"id": 3, "title": "Contact support", "body": "Reach support 24/7 via live chat."},
    {"id": 4, "title": "Password reset", "body": "Click the link on the login page."},
    {"id": 5, "title": "Order tracking", "body": "Tracking number sent by email."},
]


@pytest.fixture()
def supabase_table():
    """Insert seed rows into a Supabase table, clean them up after the test.

    If SUPABASE_TEST_TABLE is set, use that pre-existing table and assume the
    project does not allow ad-hoc DDL via PostgREST. Otherwise, attempt to use
    a table named "moss_test_<uuid>" — note that supabase-py cannot create
    tables (no DDL over PostgREST), so the user must set SUPABASE_TEST_TABLE
    pointing at a manually-created table.
    """
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    if not PRESET_TABLE:
        pytest.skip(
            "Set SUPABASE_TEST_TABLE to a pre-existing table with id (int) "
            "and body (text) columns; supabase-py cannot create tables over "
            "PostgREST."
        )

    table_name = PRESET_TABLE
    inserted_ids = [r["id"] for r in _SEED_ROWS]
    try:
        client.table(table_name).upsert(_SEED_ROWS).execute()
        yield table_name
    finally:
        try:
            client.table(table_name).delete().in_("id", inserted_ids).execute()
        except Exception as exc:  # pragma: no cover, best-effort cleanup
            print(f"warning: failed to clean up rows in {table_name}: {exc}")


async def test_supabase_ingest_end_to_end(supabase_table):
    """Full round trip: Supabase → Moss index → query → delete."""
    table_name = supabase_table
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    index_name = f"moss-supabase-e2e-{uuid.uuid4().hex[:8]}"

    try:
        connector = SupabaseConnector(
            url=SUPABASE_URL,
            key=SUPABASE_KEY,
            table=table_name,
            mapper=lambda r: DocumentInfo(
                id=str(r["id"]),
                text=r["body"],
                metadata={"title": r["title"]},
            ),
        )

        result = await ingest(connector, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count >= 5

        await client.load_index(index_name)
        result = await client.query(index_name, "how long do refunds take", QueryOptions(top_k=3))

        assert result.docs, "expected at least one document in the search result"
        top_ids = [d.id for d in result.docs]
        assert "1" in top_ids, f"refund-policy doc not in top 3: {top_ids}"

        refund_doc = next(d for d in result.docs if d.id == "1")
        assert refund_doc.metadata is not None
        assert refund_doc.metadata.get("title") == "Refund policy"

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to delete test index {index_name}: {exc}")
