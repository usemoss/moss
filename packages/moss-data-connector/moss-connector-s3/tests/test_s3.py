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


@dataclass
class FakeMossClient:
    calls: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        docs = list(docs)
        self.calls.append({"name": name, "docs": docs, "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)

    async def delete_index(self, name):
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


async def test_snapshot_respects_filters(s3_bucket):
    source = S3Connector(
        bucket=BUCKET, mapper=_simple_mapper, prefix="docs/", suffix=".md", region_name=REGION
    )
    assert set(source.snapshot()) == {"docs/refunds.md", "docs/shipping.md"}


async def test_watch_reindexes_on_change(s3_bucket):
    """watch() ingests once, then re-ingests when the bucket changes."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)
    changes: list[dict[str, str]] = []

    async def sleep_then_mutate(_seconds):
        s3_bucket.put_object(Bucket=BUCKET, Key="docs/new.md", Body=b"Newly added document.")

    with (
        patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_mutate),
    ):
        reindexed = await watch(
            source,
            "fake_id",
            "fake_key",
            "docs",
            poll_interval=0,
            max_polls=1,
            on_change=changes.append,
        )

    assert reindexed == 1
    assert len(fake_moss.calls) == 2  # initial ingest + one re-index
    assert len(fake_moss.calls[0]["docs"]) == 4
    second_keys = {d.id for d in fake_moss.calls[1]["docs"]}
    assert "docs/new.md" in second_keys
    assert changes and "docs/new.md" in changes[0]


async def test_watch_deletes_index_when_bucket_emptied(s3_bucket):
    """Emptying the bucket must delete the index, not leave stale docs searchable."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_then_empty(_seconds):
        for key in list(SAMPLE_OBJECTS):
            s3_bucket.delete_object(Bucket=BUCKET, Key=key)

    with (
        patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_empty),
    ):
        reindexed = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=1
        )

    assert reindexed == 1
    assert len(fake_moss.calls) == 1  # only the initial ingest created an index
    assert fake_moss.deleted == ["docs"]


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
        patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_then_mutate),
    ):
        reindexed = await watch(
            source,
            "fake_id",
            "fake_key",
            "docs",
            poll_interval=0,
            max_polls=1,
            on_change=async_on_change,
        )

    assert reindexed == 1
    assert awaited and "docs/new.md" in awaited[0]


async def test_watch_no_change_no_reindex(s3_bucket):
    """watch() does not re-ingest when the bucket is unchanged."""
    fake_moss = FakeMossClient()
    source = S3Connector(bucket=BUCKET, mapper=_simple_mapper, region_name=REGION)

    async def sleep_noop(_seconds):
        return None

    with (
        patch("moss_connector_s3.ingest.MossClient", return_value=fake_moss),
        patch("moss_connector_s3.watch.asyncio.sleep", side_effect=sleep_noop),
    ):
        reindexed = await watch(
            source, "fake_id", "fake_key", "docs", poll_interval=0, max_polls=3
        )

    assert reindexed == 0
    assert len(fake_moss.calls) == 1  # only the initial ingest
