"""Unit tests for ingest() against SQLite and in-memory sources. No network."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

import pytest

from moss_connectors import DocumentMapping, ingest
from moss_connectors.connectors.sqlite import SQLiteConnector


@dataclass
class FakeMossClient:
    """Stand-in for moss.MossClient that captures what would be uploaded."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        self.calls.append({"name": name, "docs": list(docs), "model_id": model_id})


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


async def test_ingest_creates_index(sqlite_db):
    source = SQLiteConnector(database=sqlite_db, query="SELECT id, title, body FROM articles")
    mapping = DocumentMapping(id="id", text="body", metadata=["title"])
    client = FakeMossClient()

    count = await ingest(source, mapping, client, index_name="articles")

    assert count == 3
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["name"] == "articles"
    assert len(call["docs"]) == 3
    assert call["docs"][0].id == "1"
    assert call["docs"][0].text == "Body for article 1"
    assert call["docs"][0].metadata == {"title": "Title 1"}


async def test_empty_source_skips_network_call():
    client = FakeMossClient()
    count = await ingest([], DocumentMapping(id="id", text="body"), client, "empty")
    assert count == 0
    assert client.calls == []


async def test_embedding_passthrough():
    """A source that carries vectors (e.g. Pinecone export) routes them through."""
    source = [
        {"id": "a", "body": "hi", "vec": [0.1, 0.2, 0.3]},
        {"id": "b", "body": "bye", "vec": [0.4, 0.5, 0.6]},
    ]
    mapping = DocumentMapping(id="id", text="body", embedding="vec")
    client = FakeMossClient()

    await ingest(source, mapping, client, index_name="vecs")

    docs = client.calls[0]["docs"]
    # Moss stores embeddings as float32, so compare with tolerance.
    assert docs[0].embedding == pytest.approx([0.1, 0.2, 0.3], rel=1e-6)
    assert docs[1].embedding == pytest.approx([0.4, 0.5, 0.6], rel=1e-6)


