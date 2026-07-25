from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("zeroentropy")

from moss import DocumentInfo  # noqa: E402
from moss_connector_zeroentropy import (  # noqa: E402
    ZeroEntropyConnector,
    coerce_metadata,
    ingest,
)


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


def _doc(path: str, *, id: str | None = None, metadata: dict | None = None) -> SimpleNamespace:
    """A stand-in for a ZeroEntropy get_info_list item."""
    return SimpleNamespace(
        id=id or f"id-{path}",
        path=path,
        metadata=metadata or {},
        file_url=f"https://files.zeroentropy.dev/{path}",
        index_status="indexed",
        num_pages=1,
        size=len(path),
    )


def _fake_ze_client(docs: list[SimpleNamespace], contents: dict[str, str | None]) -> MagicMock:
    """Build a mock ZeroEntropy client.

    ``docs`` are the items yielded by ``documents.get_info_list``; ``contents``
    maps a document path to the text ``documents.get_info(..., include_content=True)``
    returns on ``.document.content``.
    """
    client = MagicMock()
    client.documents.get_info_list.return_value = list(docs)

    def _get_info(collection_name, path, include_content):
        return SimpleNamespace(document=SimpleNamespace(content=contents.get(path)))

    client.documents.get_info.side_effect = _get_info
    return client


async def test_default_mapper_end_to_end():
    docs = [
        _doc("faq/refunds.txt", metadata={"title": "Refunds", "tags": ["billing", "policy"]}),
        _doc("faq/shipping.txt", metadata={"title": "Shipping"}),
    ]
    contents = {
        "faq/refunds.txt": "Refunds take 3 to 5 business days.",
        "faq/shipping.txt": "Orders ship within 24 hours.",
    }
    fake_ze = _fake_ze_client(docs, contents)
    fake_moss = FakeMossClient()

    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        source = ZeroEntropyConnector(collection_name="support", api_key="ze-key")
        result = await ingest(source, "pid", "pkey", index_name="support")

    assert result is not None
    assert result.doc_count == 2
    moss_docs = fake_moss.calls[0]["docs"]
    assert moss_docs[0].id == "faq/refunds.txt"
    assert moss_docs[0].text == "Refunds take 3 to 5 business days."
    # a list metadata value is joined into a single string for Moss
    assert moss_docs[0].metadata == {"title": "Refunds", "tags": "billing, policy"}
    assert moss_docs[1].id == "faq/shipping.txt"


async def test_skips_documents_without_content():
    docs = [_doc("a.txt"), _doc("b.txt"), _doc("c.txt")]
    contents = {"a.txt": "alpha", "b.txt": None, "c.txt": "gamma"}  # b never parsed
    fake_ze = _fake_ze_client(docs, contents)
    fake_moss = FakeMossClient()

    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        source = ZeroEntropyConnector(collection_name="c")
        result = await ingest(source, "pid", "pkey", "idx")

    assert result.doc_count == 2
    assert [d.id for d in fake_moss.calls[0]["docs"]] == ["a.txt", "c.txt"]


async def test_custom_mapper_sees_full_row():
    docs = [_doc("doc1", id="uuid-1", metadata={"lang": "en"})]
    fake_ze = _fake_ze_client(docs, {"doc1": "hello"})
    fake_moss = FakeMossClient()
    seen: dict[str, Any] = {}

    def mapper(row):
        seen.update(row)
        return DocumentInfo(
            id=row["id"], text=row["content"], metadata={"lang": row["metadata"]["lang"]}
        )

    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        source = ZeroEntropyConnector(collection_name="c", mapper=mapper)
        await ingest(source, "pid", "pkey", "idx")

    doc = fake_moss.calls[0]["docs"][0]
    assert doc.id == "uuid-1"
    assert doc.text == "hello"
    # the row dict exposes ZeroEntropy fields to the mapper
    assert seen["path"] == "doc1"
    assert seen["file_url"].endswith("doc1")
    assert seen["index_status"] == "indexed"
    assert seen["content"] == "hello"


async def test_include_content_false_skips_get_info():
    docs = [_doc("x", metadata={"title": "X"})]
    fake_ze = _fake_ze_client(docs, {})
    fake_moss = FakeMossClient()

    def mapper(row):
        return DocumentInfo(id=row["path"], text=row["metadata"]["title"])

    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        source = ZeroEntropyConnector(collection_name="c", mapper=mapper, include_content=False)
        result = await ingest(source, "pid", "pkey", "idx")

    assert result.doc_count == 1
    fake_ze.documents.get_info.assert_not_called()


def test_include_content_false_with_default_mapper_raises():
    # The default mapper reads content, so opting out without a custom mapper
    # would silently index empty documents; the connector must reject it.
    with pytest.raises(ValueError, match="include_content=False"):
        ZeroEntropyConnector(collection_name="c", include_content=False)


async def test_path_prefix_forwarded():
    fake_ze = _fake_ze_client([], {})
    with patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze):
        list(ZeroEntropyConnector(collection_name="c", path_prefix="faq/"))
    fake_ze.documents.get_info_list.assert_called_once_with(collection_name="c", path_prefix="faq/")


async def test_no_path_prefix_omits_kwarg():
    fake_ze = _fake_ze_client([], {})
    with patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze):
        list(ZeroEntropyConnector(collection_name="c"))
    fake_ze.documents.get_info_list.assert_called_once_with(collection_name="c")


async def test_empty_collection_skips_moss_call():
    fake_ze = _fake_ze_client([], {})
    fake_moss = FakeMossClient()
    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        result = await ingest(ZeroEntropyConnector(collection_name="empty"), "pid", "pkey", "empty")
    assert result is None
    assert fake_moss.calls == []


async def test_auto_id_replaces_path_ids():
    docs = [_doc("a"), _doc("b")]
    fake_ze = _fake_ze_client(docs, {"a": "A", "b": "B"})
    fake_moss = FakeMossClient()
    with (
        patch("moss_connector_zeroentropy.connector.ZeroEntropy", return_value=fake_ze),
        patch("moss_connector_zeroentropy.ingest.MossClient", return_value=fake_moss),
    ):
        await ingest(ZeroEntropyConnector(collection_name="c"), "pid", "pkey", "idx", auto_id=True)

    docs_out = fake_moss.calls[0]["docs"]
    for d in docs_out:
        assert uuid.UUID(d.id)  # replaced, not the path
    assert [d.text for d in docs_out] == ["A", "B"]


def test_coerce_metadata():
    assert coerce_metadata({"a": "x", "tags": ["1", "2"]}) == {"a": "x", "tags": "1, 2"}
    assert coerce_metadata(None) == {}
    assert coerce_metadata({}) == {}
