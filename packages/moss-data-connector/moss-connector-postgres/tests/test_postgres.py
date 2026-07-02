"""Unit tests for the Postgres connector. No live Postgres needed — we mock
``psycopg.connect`` so the test runs anywhere psycopg is importable, and
we patch ``moss.MossClient`` inside ingest so no Moss network call is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("psycopg")

from moss import DocumentInfo  # noqa: E402
from moss_connector_postgres import PostgresConnector, ingest  # noqa: E402


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


def _mock_cursor_returning(rows: list[dict[str, Any]]) -> MagicMock:
    """Build a mock cursor that yields *rows* when iterated."""
    cursor = MagicMock()
    cursor.__iter__ = MagicMock(return_value=iter(rows))
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _mock_conn_returning(cursor: MagicMock) -> MagicMock:
    """Build a mock psycopg connection whose ``cursor()`` returns *cursor*."""
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


async def test_postgres_ingest_end_to_end():
    rows_from_postgres = [
        {"id": 1, "title": "Refund policy", "body": "Refunds take 3–5 days."},
        {"id": 2, "title": "Shipping", "body": "We ship within 24 hours."},
        {"id": 3, "title": "Returns", "body": "Returns accepted within 30 days."},
    ]
    cursor = _mock_cursor_returning(rows_from_postgres)
    fake_conn = _mock_conn_returning(cursor)
    fake_moss = FakeMossClient()

    with patch("moss_connector_postgres.connector.psycopg.connect", return_value=fake_conn), patch(
        "moss_connector_postgres.ingest.MossClient", return_value=fake_moss
    ):
        source = PostgresConnector(
            dsn="postgresql://user:pass@localhost:5432/shop",
            query="SELECT id, title, body FROM articles",
            mapper=lambda r: DocumentInfo(
                id=str(r["id"]),
                text=r["body"],
                metadata={"title": r["title"]},
            ),
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 3
    assert len(fake_moss.calls) == 1

    moss_docs = fake_moss.calls[0]["docs"]
    assert moss_docs[0].id == "1"
    assert moss_docs[0].text == "Refunds take 3–5 days."
    assert moss_docs[0].metadata == {"title": "Refund policy"}
    assert moss_docs[2].id == "3"


async def test_empty_result_skips_network_call():
    cursor = _mock_cursor_returning([])
    fake_conn = _mock_conn_returning(cursor)
    fake_moss = FakeMossClient()

    with patch("moss_connector_postgres.connector.psycopg.connect", return_value=fake_conn), patch(
        "moss_connector_postgres.ingest.MossClient", return_value=fake_moss
    ):
        source = PostgresConnector(
            dsn="postgresql://user:pass@localhost:5432/empty_db",
            query="SELECT id, body FROM articles",
            mapper=lambda r: DocumentInfo(id=str(r["id"]), text=r["body"]),
        )
        result = await ingest(source, "fake_id", "fake_key", "empty")

    assert result is None
    assert fake_moss.calls == []


async def test_dsn_forwarded_to_psycopg_connect():
    """Verify that the DSN is forwarded to psycopg.connect."""
    cursor = _mock_cursor_returning([])
    fake_conn = _mock_conn_returning(cursor)
    patch_target = "moss_connector_postgres.connector.psycopg.connect"

    dsn = "postgresql://app:hunter2@db.example.com:5432/prod"

    with patch(patch_target, return_value=fake_conn) as mock_connect:
        source = PostgresConnector(
            dsn=dsn,
            query="SELECT 1",
            mapper=lambda r: DocumentInfo(id="x", text="y"),
        )
        list(source)  # exhaust the iterator to trigger connect()

    mock_connect.assert_called_once()
    call_args = mock_connect.call_args
    assert call_args[0][0] == dsn


async def test_auto_id_generates_uuids():
    rows_from_postgres = [
        {"title": "A", "body": "First"},
        {"title": "B", "body": "Second"},
    ]
    cursor = _mock_cursor_returning(rows_from_postgres)
    fake_conn = _mock_conn_returning(cursor)
    fake_moss = FakeMossClient()

    with patch("moss_connector_postgres.connector.psycopg.connect", return_value=fake_conn), patch(
        "moss_connector_postgres.ingest.MossClient", return_value=fake_moss
    ):
        source = PostgresConnector(
            dsn="postgresql://localhost/db",
            query="SELECT title, body FROM articles",
            mapper=lambda r: DocumentInfo(id="", text=r["body"]),
        )
        result = await ingest(source, "fake_id", "fake_key", "articles", auto_id=True)

    assert result is not None
    assert result.doc_count == 2
    # auto_id should have replaced empty ids with UUIDs
    ids = [doc.id for doc in fake_moss.calls[0]["docs"]]
    assert all(len(id) == 36 for id in ids)  # UUIDs are 36 chars
    assert ids[0] != ids[1]  # unique