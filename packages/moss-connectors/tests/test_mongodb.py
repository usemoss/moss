"""Unit tests for the MongoDB connector. No live MongoDB needed — we mock
`pymongo.MongoClient` so the test runs anywhere pymongo is importable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pymongo")

from moss_connectors import DocumentMapping, ingest  # noqa: E402
from moss_connectors.connectors.mongodb import MongoDBConnector  # noqa: E402


@dataclass
class FakeMossClient:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        self.calls.append({"name": name, "docs": list(docs), "model_id": model_id})


def _mongo_mock_returning(docs: list[dict[str, Any]]) -> tuple[MagicMock, MagicMock]:
    """Build a mock `MongoClient(...)` that returns `docs` from its find() call.

    Returns (client, collection) so the test can assert on either one —
    `client` for passing to `patch("pymongo.MongoClient", return_value=...)`,
    `collection` for inspecting how `find()` was called.
    """
    collection = MagicMock()
    collection.find.return_value = iter(docs)
    db = MagicMock()
    db.__getitem__.return_value = collection
    client = MagicMock()
    client.__getitem__.return_value = db
    return client, collection


async def test_mongodb_ingest_end_to_end():
    docs_from_mongo = [
        {"_id": "a1", "title": "Refund policy", "body": "Refunds take 3–5 days."},
        {"_id": "a2", "title": "Shipping", "body": "We ship within 24 hours."},
    ]
    fake_client, fake_collection = _mongo_mock_returning(docs_from_mongo)

    with patch("pymongo.MongoClient", return_value=fake_client):
        source = MongoDBConnector(
            uri="mongodb://localhost",
            database="shop",
            collection="articles",
        )
        mapping = DocumentMapping(id="_id", text="body", metadata=["title"])
        moss_client = FakeMossClient()

        count = await ingest(source, mapping, moss_client, index_name="articles")

    assert count == 2

    # Collection.find() was called with the default filter/projection.
    fake_collection.find.assert_called_once_with({}, None)

    moss_docs = moss_client.calls[0]["docs"]
    assert moss_docs[0].id == "a1"
    assert moss_docs[0].text == "Refunds take 3–5 days."
    assert moss_docs[0].metadata == {"title": "Refund policy"}


async def test_mongodb_forwards_filter_and_projection():
    fake_client, fake_collection = _mongo_mock_returning([])

    my_filter = {"status": "published"}
    my_projection = {"_id": 1, "body": 1, "title": 1}

    with patch("pymongo.MongoClient", return_value=fake_client):
        source = MongoDBConnector(
            uri="mongodb://localhost",
            database="shop",
            collection="articles",
            filter=my_filter,
            projection=my_projection,
        )
        await ingest(
            source,
            DocumentMapping(id="_id", text="body"),
            FakeMossClient(),
            index_name="x",
        )

    fake_collection.find.assert_called_once_with(my_filter, my_projection)
