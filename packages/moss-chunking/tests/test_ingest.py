"""`refresh_source` tests.

Upsert alone cannot reconcile: a document that cuts into fewer chunks than it
used to leaves the old tail behind, still searchable, holding text that is no
longer in the document. These tests are about that tail — that it is found, that
it is deleted before the new chunks land, and that a document which did not
shrink pays one lookup for the privilege and nothing more.

The client is a fake. Everything under test is which calls get made and in what
order, which is exactly what a fake can answer and a live index cannot cheaply.
"""

from __future__ import annotations

import pytest
from moss import DocumentInfo
from moss_chunking import CharSplitter, chunk_document, chunk_id, refresh_source

PROSE = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi"


class FakeClient:
    """Enough of `MossClient` for the refresh path, recording what it was asked."""

    def __init__(self, existing: list[str] | None = None) -> None:
        self.existing = set(existing or [])
        self.calls: list[tuple[str, object]] = []

    async def get_docs(self, name, options=None):
        self.calls.append(("get_docs", list(options.doc_ids)))
        return [
            DocumentInfo(id=doc_id, text="stale")
            for doc_id in options.doc_ids
            if doc_id in self.existing
        ]

    async def delete_docs(self, name, doc_ids):
        self.calls.append(("delete_docs", list(doc_ids)))
        self.existing -= set(doc_ids)
        return None

    async def add_docs(self, name, docs, options=None):
        self.calls.append(("add_docs", [d.id for d in docs]))
        self.existing |= {d.id for d in docs}
        return "added"


def ids_for(source: str, count: int) -> list[str]:
    return [chunk_id(source, index) for index in range(count)]


def deleted(client: FakeClient) -> list[str]:
    return [doc_id for kind, arg in client.calls if kind == "delete_docs" for doc_id in arg]


async def test_a_shrunken_document_loses_its_stale_tail():
    """The case upsert cannot handle: 21 chunks re-cut into 6."""
    client = FakeClient(existing=ids_for("notes.md", 21))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 6)]

    await refresh_source(client, "idx", "notes.md", docs)

    assert deleted(client) == ids_for("notes.md", 21)[6:]
    assert client.existing == set(ids_for("notes.md", 6))


async def test_the_tail_is_deleted_before_the_new_chunks_land():
    """Ordering matters: an add that fails must not leave the stale tail behind."""
    client = FakeClient(existing=ids_for("notes.md", 9))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 2)]

    await refresh_source(client, "idx", "notes.md", docs)

    kinds = [kind for kind, _ in client.calls]
    assert kinds.index("delete_docs") < kinds.index("add_docs")


async def test_a_document_that_did_not_shrink_deletes_nothing():
    client = FakeClient(existing=ids_for("notes.md", 4))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 4)]

    result = await refresh_source(client, "idx", "notes.md", docs)

    assert result == "added"
    assert [kind for kind, _ in client.calls] == ["get_docs", "add_docs"]


async def test_a_grown_document_costs_a_single_lookup():
    """One probe past the end proves there is no tail; no scan of the index."""
    client = FakeClient(existing=ids_for("notes.md", 2))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 5)]

    await refresh_source(client, "idx", "notes.md", docs)

    assert [kind for kind, _ in client.calls].count("get_docs") == 1


async def test_passing_no_documents_removes_the_source_entirely():
    """How a deleted file leaves the index."""
    client = FakeClient(existing=ids_for("notes.md", 3) + ids_for("other.md", 2))

    result = await refresh_source(client, "idx", "notes.md", [])

    assert result is None
    assert client.existing == set(ids_for("other.md", 2))


async def test_another_sources_chunks_are_never_touched():
    client = FakeClient(existing=ids_for("notes.md", 8) + ids_for("other.md", 8))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 1)]

    await refresh_source(client, "idx", "notes.md", docs)

    assert set(ids_for("other.md", 8)) <= client.existing
    assert not any(doc_id.startswith("other.md") for doc_id in deleted(client))


async def test_a_tail_longer_than_one_probe_window_is_still_cleared():
    """The window is a batch size, not a ceiling: probing continues while it hits."""
    client = FakeClient(existing=ids_for("notes.md", 600))
    docs = [DocumentInfo(id=doc_id, text="fresh") for doc_id in ids_for("notes.md", 1)]

    await refresh_source(client, "idx", "notes.md", docs)

    assert client.existing == set(ids_for("notes.md", 1))
    assert len(deleted(client)) == 599


@pytest.mark.parametrize("cut", [40, 12])
async def test_refresh_is_idempotent_for_real_chunked_output(cut):
    """Twice through with the same text changes nothing the second time."""
    client = FakeClient()
    docs = chunk_document(PROSE, "notes.md", CharSplitter(chunk_chars=cut, overlap=5))

    await refresh_source(client, "idx", "notes.md", docs)
    after_first = set(client.existing)
    await refresh_source(client, "idx", "notes.md", docs)

    assert client.existing == after_first
    assert not deleted(client)
