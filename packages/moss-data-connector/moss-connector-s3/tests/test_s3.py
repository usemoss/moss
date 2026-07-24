"""Unit tests for the S3 connector.

No live AWS needed — we mock S3 with ``moto`` so the test runs anywhere
``boto3`` and ``moto[s3]`` are importable, and we patch ``moss.MossClient``
inside ingest so no Moss network call is made.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import boto3
import pytest

pytest.importorskip("moto")

from moss import DocumentInfo  # noqa: E402
from moss_connector_s3 import S3Connector, ingest, watch  # noqa: E402
from moto import mock_aws  # noqa: E402

# ---------------------------------------------------------------------------
# Fake Moss client
# ---------------------------------------------------------------------------

BUCKET = "moss-connector-test"
REGION = "us-east-1"


@dataclass
class FakeMutationResult:
    doc_count: int
    job_id: str = "fake-job-id"
    index_name: str = ""


class _FakeIndexInfo:
    def __init__(self, name: str) -> None:
        self.name = name


@dataclass
class FakeMossClient:
    """Stateful fake mimicking the real client's strictness: create_index is
    create-only, and every other mutation raises when the index is absent.
    Documents are stored per index so upserts and deletes can be verified."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    indexes: dict[str, dict[str, DocumentInfo]] = field(default_factory=dict)

    @property
    def existing(self) -> set[str]:
        return set(self.indexes)

    def docs_in(self, name: str) -> dict[str, DocumentInfo]:
        return self.indexes[name]

    async def create_index(self, name, docs, model_id=None):
        if name in self.indexes:
            raise ValueError(f"index '{name}' already exists")
        docs = list(docs)
        self.indexes[name] = {d.id: d for d in docs}
        self.calls.append({"op": "create", "name": name, "docs": docs, "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)

    async def add_docs(self, name, docs, options=None):
        if name not in self.indexes:
            raise ValueError(f"index '{name}' not found")
        docs = list(docs)
        self.indexes[name].update({d.id: d for d in docs})
        self.calls.append({"op": "add", "name": name, "docs": docs, "options": options})
        return FakeMutationResult(doc_count=len(docs), index_name=name)

    async def delete_docs(self, name, doc_ids):
        if name not in self.indexes:
            raise ValueError(f"index '{name}' not found")
        for doc_id in doc_ids:
            self.indexes[name].pop(doc_id, None)
        self.calls.append({"op": "delete_docs", "name": name, "doc_ids": list(doc_ids)})
        return FakeMutationResult(doc_count=len(doc_ids), index_name=name)

    async def get_docs(self, name, options=None):
        if name not in self.indexes:
            raise ValueError(f"index '{name}' not found")
        return list(self.indexes[name].values())

    async def list_indexes(self):
        return [_FakeIndexInfo(name) for name in self.indexes]

    async def delete_index(self, name):
        if name not in self.indexes:
            raise ValueError(f"index '{name}' not found")
        del self.indexes[name]
        self.deleted.append(name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_OBJECTS = {
    "docs/refunds.md": "Refunds are processed within 3 to 5 business days.",
    "docs/shipping.md": "Most orders ship within 24 hours of being placed.",
    "docs/support.txt": "You can reach our support team 24/7 via live chat.",
    "images/logo.png": "not-really-a-png",
}


@pytest.fixture()
def s3_bucket():
    """Spin up a moto-mocked S3 bucket and populate it with SAMPLE_OBJECTS."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET)
        for key, body in SAMPLE_OBJECTS.items():
            s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
        yield s3


def _simple_mapper(row: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=row["key"],
        text=row["text"],
        metadata={"etag": row["etag"], "size": str(row["size"])},
    )


# ---------------------------------------------------------------------------
# S3Connector tests
# ---------------------------------------------------------------------------


async def test_ingest_end_to_end(s3_bucket):
    fake_moss = FakeMossClient()

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
        result = await ingest(source, "fake_id", "fake_key", index_name="docs")

    assert result is not None
    assert result.doc_count == 4

    docs = fake_moss.calls[0]["docs"]
    keys = {d.id for d in docs}
    assert keys == set(SAMPLE_OBJECTS)

    refund = next(d for d in docs if d.id == "docs/refunds.md")
    assert refund.text == "Refunds are processed within 3 to 5 business days."
    assert refund.metadata["size"] == str(len(SAMPLE_OBJECTS["docs/refunds.md"]))
    assert refund.metadata["etag"]  # non-empty, quotes stripped
    assert not refund.metadata["etag"].startswith('"')


async def test_prefix_filter(s3_bucket):
    fake_moss = FakeMossClient()

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        source = S3Connector(
            bucket=BUCKET, mapper=_simple_mapper, prefix="docs/", region_name=REGION
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="docs")

    assert result is not None
    assert result.doc_count == 3
    assert all(d.id.startswith("docs/") for d in fake_moss.calls[0]["docs"])


async def test_suffix_filter(s3_bucket):
    fake_moss = FakeMossClient()

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        source = S3Connector(
            bucket=BUCKET, mapper=_simple_mapper, suffix=(".md", ".txt"), region_name=REGION
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="docs")

    assert result is not None
    assert result.doc_count == 3
    assert "images/logo.png" not in {d.id for d in fake_moss.calls[0]["docs"]}


async def test_folder_placeholders_skipped(s3_bucket):
    """Zero-byte keys ending in '/' (console-created folders) are never yielded."""
    s3_bucket.put_object(Bucket=BUCKET, Key="docs/", Body=b"")

    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
    keys = {doc.id for doc in source}
    assert "docs/" not in keys
    assert len(keys) == 4


async def test_pagination(s3_bucket):
    """page_size=1 forces multiple list pages; all objects still arrive."""
    fake_moss = FakeMossClient()

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        source = S3Connector(
            bucket=BUCKET, mapper=_simple_mapper, page_size=1, region_name=REGION
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="docs")

    assert result is not None
    assert result.doc_count == 4


async def test_object_user_metadata_reaches_mapper(s3_bucket):
    s3_bucket.put_object(
        Bucket=BUCKET,
        Key="docs/tagged.md",
        Body=b"Tagged document body.",
        ContentType="text/markdown",
        Metadata={"author": "ada"},
    )

    seen: dict[str, Any] = {}

    def capture(row: dict[str, Any]) -> DocumentInfo:
        if row["key"] == "docs/tagged.md":
            seen.update(row)
        return _simple_mapper(row)

    source = S3Connector(bucket=BUCKET, mapper=capture, region_name=REGION)
    list(source)

    assert seen["metadata"] == {"author": "ada"}
    assert seen["content_type"] == "text/markdown"
    assert seen["last_modified"] is not None


async def test_empty_bucket():
    """ingest() returns None when the bucket is empty."""
    fake_moss = FakeMossClient()

    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="empty")

        with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
            source = S3Connector(bucket="empty", mapper=_simple_mapper, region_name=REGION)
            result = await ingest(source, "fake_id", "fake_key", index_name="empty")

    assert result is None
    assert fake_moss.calls == []


async def test_ingest_accepts_plain_iterables():
    """The exported ingest() wraps the shared one; pre-materialized docs work too."""
    fake_moss = FakeMossClient()
    docs = [DocumentInfo(id="a", text="alpha"), DocumentInfo(id="b", text="beta")]

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        result = await ingest(docs, "fake_id", "fake_key", index_name="plain")

    assert result is not None
    assert result.doc_count == 2
    assert {d.id for d in fake_moss.calls[0]["docs"]} == {"a", "b"}


async def test_auto_id_replaces_mapper_id(s3_bucket):
    fake_moss = FakeMossClient()

    with patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss):
        source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
        await ingest(source, "fake_id", "fake_key", index_name="docs", auto_id=True)

    docs = fake_moss.calls[0]["docs"]
    assert len(docs) == 4
    for doc in docs:
        assert doc.id
        assert uuid.UUID(doc.id)  # valid UUID4
        assert doc.id not in SAMPLE_OBJECTS


# ---------------------------------------------------------------------------
# snapshot() and watch() tests
# ---------------------------------------------------------------------------


async def test_snapshot_tracks_add_modify_delete(s3_bucket):
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    before = source.snapshot()
    assert set(before) == set(SAMPLE_OBJECTS)

    s3_bucket.put_object(Bucket=BUCKET, Key="docs/new.md", Body=b"Brand new document.")
    s3_bucket.put_object(Bucket=BUCKET, Key="docs/refunds.md", Body=b"Refunds now take 7 days.")
    s3_bucket.delete_object(Bucket=BUCKET, Key="docs/support.txt")

    after = source.snapshot()
    assert "docs/new.md" in after
    assert "docs/support.txt" not in after
    assert after["docs/refunds.md"] != before["docs/refunds.md"]  # ETag changed


async def test_snapshot_marker_includes_last_modified(s3_bucket):
    """Markers pair ETag with LastModified/Size so metadata-only rewrites are seen."""
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
    head = s3_bucket.head_object(Bucket=BUCKET, Key="docs/refunds.md")

    marker = source.snapshot()["docs/refunds.md"]
    assert marker.startswith(f"{head['ETag'].strip(chr(34))}|")
    assert head["LastModified"].isoformat() in marker
    assert marker.endswith(str(head["ContentLength"]))


async def test_snapshot_respects_filters(s3_bucket):
    source = S3Connector(
        bucket=BUCKET, mapper=_simple_mapper, prefix="docs/", suffix=".md", region_name=REGION
    )
    assert set(source.snapshot()) == {"docs/refunds.md", "docs/shipping.md"}


async def test_watch_added_object_syncs_incrementally(s3_bucket):
    """A new object is upserted on its own — the index is never rebuilt."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
    changes: list[dict[str, str]] = []

    async def sleep_then_mutate(_seconds):
        s3_bucket.put_object(Bucket=BUCKET, Key="docs/new.md", Body=b"Newly added document.")

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_mutate),
    ):
        synced = await watch(
            source,
            "fake_id",
            "fake_key",
            "docs",
            poll_interval=0,
            max_polls=1,
            on_change=changes.append,
        )

    assert synced == 1
    assert fake_moss.deleted == []  # the live index was never dropped
    assert [c["op"] for c in fake_moss.calls] == ["create", "add"]
    assert len(fake_moss.calls[0]["docs"]) == 4  # initial create: whole bucket
    add_docs = fake_moss.calls[1]["docs"]
    assert [d.id for d in add_docs] == ["docs/new.md"]  # only the diff was pushed
    assert set(fake_moss.docs_in("docs")) == set(SAMPLE_OBJECTS) | {"docs/new.md"}
    assert changes and "docs/new.md" in changes[0]


async def test_watch_modified_object_upserts_only_that_doc(s3_bucket):
    """An overwritten object is re-pushed alone, with its new content."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_then_overwrite(_seconds):
        s3_bucket.put_object(
            Bucket=BUCKET, Key="docs/refunds.md", Body=b"Refunds now take 7 days."
        )

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_overwrite),
    ):
        synced = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1
        )

    assert synced == 1
    assert [c["op"] for c in fake_moss.calls] == ["create", "add"]
    assert [d.id for d in fake_moss.calls[1]["docs"]] == ["docs/refunds.md"]
    assert fake_moss.docs_in("docs")["docs/refunds.md"].text == "Refunds now take 7 days."
    assert len(fake_moss.docs_in("docs")) == 4  # no duplicates


async def test_watch_removed_object_deletes_only_that_doc(s3_bucket):
    """A deleted object is removed by id — the other docs stay untouched."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_then_remove(_seconds):
        s3_bucket.delete_object(Bucket=BUCKET, Key="docs/support.txt")

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_remove),
    ):
        synced = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1
        )

    assert synced == 1
    assert [c["op"] for c in fake_moss.calls] == ["create", "delete_docs"]
    assert fake_moss.calls[1]["doc_ids"] == ["docs/support.txt"]
    assert set(fake_moss.docs_in("docs")) == set(SAMPLE_OBJECTS) - {"docs/support.txt"}
    assert fake_moss.deleted == []


async def test_watch_deletes_index_when_bucket_emptied(s3_bucket):
    """Emptying the bucket must delete the index, not leave stale docs searchable."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_then_empty(_seconds):
        for key in list(SAMPLE_OBJECTS):
            s3_bucket.delete_object(Bucket=BUCKET, Key=key)

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_empty),
    ):
        synced = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1
        )

    assert synced == 1
    assert [c["op"] for c in fake_moss.calls] == ["create"]
    assert fake_moss.deleted == ["docs"]
    assert fake_moss.existing == set()  # nothing left searchable


async def test_watch_async_on_change_awaited(s3_bucket):
    """An async on_change callback is awaited, not dropped."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
    awaited: list[dict[str, str]] = []

    async def async_on_change(snapshot):
        awaited.append(snapshot)

    async def sleep_then_mutate(_seconds):
        s3_bucket.put_object(Bucket=BUCKET, Key="docs/new.md", Body=b"Newly added document.")

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_mutate),
    ):
        synced = await watch(
            source,
            "fake_id",
            "fake_key",
            "docs",
            poll_interval=0,
            max_polls=1,
            on_change=async_on_change,
        )

    assert synced == 1
    assert awaited and "docs/new.md" in awaited[0]


async def test_watch_failed_sync_keeps_old_index(s3_bucket):
    """A sync that fails mid-download must leave the live index untouched."""
    fake_moss = FakeMossClient()

    def poison_aware_mapper(row: dict[str, Any]) -> DocumentInfo:
        if row["key"] == "docs/poison.md":
            raise ValueError("bad object body")
        return _simple_mapper(row)

    source = S3Connector(bucket=BUCKET, mapper=poison_aware_mapper, region_name=REGION)

    async def sleep_then_poison(_seconds):
        s3_bucket.put_object(Bucket=BUCKET, Key="docs/poison.md", Body=b"corrupt")

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_poison),
    ):
        with pytest.raises(ValueError, match="bad object body"):
            await watch(source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1)

    assert fake_moss.existing == {"docs"}  # live index survived the failed sync
    assert fake_moss.deleted == []
    assert [c["op"] for c in fake_moss.calls] == ["create"]
    assert set(fake_moss.docs_in("docs")) == set(SAMPLE_OBJECTS)  # content intact


async def test_watch_restart_reconciles_existing_index(s3_bucket):
    """A restarted watch() reuses a surviving index: upserts current docs and
    purges stale ones, without ever deleting the index."""
    fake_moss = FakeMossClient()
    fake_moss.indexes["docs"] = {  # index survives from a previous watch() run
        "docs/refunds.md": DocumentInfo(id="docs/refunds.md", text="old refund text"),
        "docs/gone.md": DocumentInfo(id="docs/gone.md", text="object no longer in bucket"),
    }
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_noop(_seconds):
        return None

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_noop),
    ):
        synced = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1
        )

    assert synced == 0
    assert fake_moss.deleted == []  # reconciled in place, never dropped
    assert [c["op"] for c in fake_moss.calls] == ["add", "delete_docs"]
    assert fake_moss.calls[1]["doc_ids"] == ["docs/gone.md"]  # stale doc purged
    assert set(fake_moss.docs_in("docs")) == set(SAMPLE_OBJECTS)
    refund = fake_moss.docs_in("docs")["docs/refunds.md"]
    assert refund.text == SAMPLE_OBJECTS["docs/refunds.md"]  # upserted, not stale


async def test_watch_no_change_no_sync(s3_bucket):
    """watch() pushes nothing when the bucket is unchanged."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_noop(_seconds):
        return None

    with (
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_noop),
    ):
        synced = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=3
        )

    assert synced == 0
    assert [c["op"] for c in fake_moss.calls] == ["create"]  # only the initial sync
    assert fake_moss.deleted == []
