"""Unit tests for ingest() against SQLite and in-memory sources. No network.

We patch `moss_connector_sqlite.ingest.MossClient` so ingest() builds a fake client
instead of a real one.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from moss import DocumentInfo

from moss_connector_sqlite import SQLiteConnector, ingest


@dataclass
class FakeMutationResult:
    doc_count: int
    job_id: str = "fake-job-id"
    index_name: str = ""


@dataclass
class FakeMossClient:
    """Stand-in for moss.MossClient that records what would be uploaded."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        docs = list(docs)
        self.calls.append({"name": name, "docs": docs, "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)


@pytest.fixture()
def fake_client():
    """Patch MossClient inside the ingest module so it returns our fake."""
    fake = FakeMossClient()
    with patch("moss_connector_sqlite.ingest.MossClient", return_value=fake):
        yield fake


@pytest.fixture()
def sqlite_db(tmp_path):
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT, body TEXT)")
    conn.executemany(
        "INSERT INTO articles (id, title, body) VALUES (?, ?, ?)",
        [(i, f"Title {i}", f"Body for article {i}") for i in range(1, 4)],
    )
    conn.commit()
    conn.close()
    return str(path)


async def test_ingest_creates_index(sqlite_db, fake_client):
    source = SQLiteConnector(
        database=sqlite_db,
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
    assert len(fake_client.calls) == 1
    call = fake_client.calls[0]
    assert call["name"] == "articles"
    assert len(call["docs"]) == 3
    assert call["docs"][0].id == "1"
    assert call["docs"][0].text == "Body for article 1"
    assert call["docs"][0].metadata == {"title": "Title 1"}


async def test_auto_id_defaults_to_false(sqlite_db, fake_client):
    source = SQLiteConnector(
        database=sqlite_db,
        query="SELECT id, title, body FROM articles",
        mapper=lambda r: DocumentInfo(
            id=str(r["id"]),
            text=r["body"],
            metadata={"title": r["title"]},
        ),
    )

    await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert len(fake_client.calls) == 1
    docs = fake_client.calls[0]["docs"]
    assert docs[0].id == "1"
    assert docs[1].id == "2"
    assert docs[2].id == "3"


async def test_auto_id_replaces_mapper_id(sqlite_db, fake_client):
    source = SQLiteConnector(
        database=sqlite_db,
        query="SELECT id, title, body FROM articles",
        mapper=lambda r: DocumentInfo(
            id=str(r["id"]),
            text=r["body"],
            metadata={"title": r["title"]},
        ),
    )

    await ingest(
        source,
        "fake_id",
        "fake_key",
        index_name="articles",
        auto_id=True,
    )

    assert len(fake_client.calls) == 1
    docs = fake_client.calls[0]["docs"]
    assert len(docs) == 3
    original_ids = {"1", "2", "3"}
    for doc in docs:
        assert doc.id
        assert uuid.UUID(doc.id)
        assert doc.id not in original_ids
    assert [doc.text for doc in docs] == [
        "Body for article 1",
        "Body for article 2",
        "Body for article 3",
    ]
    assert [doc.metadata for doc in docs] == [
        {"title": "Title 1"},
        {"title": "Title 2"},
        {"title": "Title 3"},
    ]


async def test_empty_source_skips_network_call(fake_client):
    result = await ingest([], "fake_id", "fake_key", "empty")
    assert result is None
    assert fake_client.calls == []


async def test_embedding_passthrough(fake_client):
    """A source of pre-built DocumentInfos (e.g. from a vector DB) works directly."""
    source = [
        DocumentInfo(id="a", text="hi", embedding=[0.1, 0.2, 0.3]),
        DocumentInfo(id="b", text="bye", embedding=[0.4, 0.5, 0.6]),
    ]

    await ingest(source, "fake_id", "fake_key", index_name="vecs")

    docs = fake_client.calls[0]["docs"]
    # Moss stores embeddings as float32, so compare with tolerance.
    assert docs[0].embedding == pytest.approx([0.1, 0.2, 0.3], rel=1e-6)
    assert docs[1].embedding == pytest.approx([0.4, 0.5, 0.6], rel=1e-6)
