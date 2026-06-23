"""Unit tests for the HuggingFace dataset connector.

No network access needed — we mock ``datasets.load_dataset`` so the tests
run anywhere the ``datasets`` package is importable, and we patch
``moss.MossClient`` inside ingest so no Moss network call is made.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("datasets")

from moss import DocumentInfo  # noqa: E402
from moss_connector_huggingface import (  # noqa: E402
    HuggingFaceDatasetConnector,
    HuggingFaceLocalDatasetConnector,
    ingest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ROWS = [
    {
        "id": "r1",
        "title": "Refund policy",
        "text": "Refunds are processed within 3 to 5 business days.",
        "label": 0,
    },
    {
        "id": "r2",
        "title": "Shipping time",
        "text": "Most orders ship within 24 hours of being placed.",
        "label": 1,
    },
    {
        "id": "r3",
        "title": "Contact support",
        "text": "You can reach our support team 24/7 via live chat.",
        "label": 2,
    },
]


def _simple_mapper(row: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=row["id"],
        text=row["text"],
        metadata={"title": row["title"], "label": str(row["label"])},
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


def _mock_load_dataset(rows: list[dict[str, Any]]) -> MagicMock:
    """Return a mock that quacks like a datasets.Dataset / IterableDataset."""
    mock_ds = MagicMock()
    mock_ds.__iter__ = MagicMock(return_value=iter(rows))
    return mock_ds


# ---------------------------------------------------------------------------
# HuggingFaceDatasetConnector tests
# ---------------------------------------------------------------------------


async def test_hub_ingest_end_to_end():
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),  # type: ignore[attr-defined]
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(
            dataset_name="fake/dataset",
            mapper=_simple_mapper,
            split="train",
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="articles")

    assert result is not None
    assert result.doc_count == 3

    docs = fake_moss.calls[0]["docs"]
    assert docs[0].id == "r1"
    assert docs[0].text == "Refunds are processed within 3 to 5 business days."
    assert docs[0].metadata == {"title": "Refund policy", "label": "0"}


async def test_hub_auto_id_defaults_to_false():
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(dataset_name="fake/dataset", mapper=_simple_mapper)
        await ingest(source, "fake_id", "fake_key", index_name="articles")

    docs = fake_moss.calls[0]["docs"]
    assert [d.id for d in docs] == ["r1", "r2", "r3"]


async def test_hub_auto_id_replaces_mapper_id():
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(dataset_name="fake/dataset", mapper=_simple_mapper)
        await ingest(source, "fake_id", "fake_key", index_name="articles", auto_id=True)

    docs = fake_moss.calls[0]["docs"]
    original_ids = {"r1", "r2", "r3"}
    for doc in docs:
        assert doc.id and uuid.UUID(doc.id)
        assert doc.id not in original_ids


async def test_hub_filter_fn():
    """filter_fn should restrict yielded rows without touching load_dataset args."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(
            dataset_name="fake/dataset",
            mapper=_simple_mapper,
            filter_fn=lambda row: row["label"] == 0,  # only billing
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="billing")

    assert result is not None
    assert result.doc_count == 1
    assert fake_moss.calls[0]["docs"][0].id == "r1"


async def test_hub_empty_dataset():
    """ingest() should return None when the dataset yields no rows."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset([])

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(dataset_name="fake/dataset", mapper=_simple_mapper)
        result = await ingest(source, "fake_id", "fake_key", index_name="empty")

    assert result is None
    assert fake_moss.calls == []


async def test_hub_passes_name_and_token_to_load_dataset():
    """name= and token= must be forwarded to load_dataset."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS[:1])

    with (
        patch(
            "moss_connector_huggingface.connector.load_dataset", return_value=mock_ds
        ) as mock_load,
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(
            dataset_name="wikipedia",
            mapper=_simple_mapper,
            split="train[:10]",
            name="20220301.en",
            token="hf_test_token",
        )
        list(source)  # exhaust the iterator

    mock_load.assert_called_once()
    _, call_kwargs = mock_load.call_args
    assert call_kwargs["name"] == "20220301.en"
    assert call_kwargs["token"] == "hf_test_token"
    assert call_kwargs["split"] == "train[:10]"


async def test_hub_explicit_streaming_overrides_kwargs():
    """Explicit streaming parameter must override streaming in load_kwargs."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS[:1])

    with (
        patch(
            "moss_connector_huggingface.connector.load_dataset", return_value=mock_ds
        ) as mock_load,
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(
            dataset_name="wikipedia",
            mapper=_simple_mapper,
            streaming=True,
        )
        source.load_kwargs["streaming"] = False
        list(source)

    mock_load.assert_called_once()
    _, call_kwargs = mock_load.call_args
    assert call_kwargs["streaming"] is True  # defaults to True, overrides keyword args



# ---------------------------------------------------------------------------
# HuggingFaceLocalDatasetConnector tests
# ---------------------------------------------------------------------------


async def test_local_ingest_end_to_end():
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceLocalDatasetConnector(
            data_files="articles.jsonl",
            mapper=_simple_mapper,
            format="json",
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="local-articles")

    assert result is not None
    assert result.doc_count == 3
    docs = fake_moss.calls[0]["docs"]
    assert {d.id for d in docs} == {"r1", "r2", "r3"}


async def test_local_filter_fn():
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS)

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceLocalDatasetConnector(
            data_files="articles.jsonl",
            mapper=_simple_mapper,
            filter_fn=lambda row: row["label"] > 0,
        )
        result = await ingest(source, "fake_id", "fake_key", index_name="filtered")

    assert result is not None
    assert result.doc_count == 2
    doc_ids = {d.id for d in fake_moss.calls[0]["docs"]}
    assert doc_ids == {"r2", "r3"}


async def test_local_passes_format_and_data_files():
    """format and data_files must be forwarded correctly to load_dataset."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS[:1])

    with (
        patch(
            "moss_connector_huggingface.connector.load_dataset", return_value=mock_ds
        ) as mock_load,
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceLocalDatasetConnector(
            data_files=["train.parquet", "train2.parquet"],
            mapper=_simple_mapper,
            format="parquet",
        )
        list(source)

    mock_load.assert_called_once()
    pos_args, call_kwargs = mock_load.call_args
    assert pos_args == ("parquet",)
    assert call_kwargs["data_files"] == ["train.parquet", "train2.parquet"]


async def test_auto_mode_single_string_columns():
    """Passing a single string to text_columns/metadata_columns shouldn't split characters."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS[:1])

    with (
        patch("moss_connector_huggingface.connector.load_dataset", return_value=mock_ds),
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceDatasetConnector(
            dataset_name="fake/dataset",
            id_column="id",
            text_columns="text",
            metadata_columns="title",
        )
        await ingest(source, "fake_id", "fake_key", index_name="articles")

    docs = fake_moss.calls[0]["docs"]
    assert len(docs) == 1
    assert docs[0].text == "text: Refunds are processed within 3 to 5 business days.."
    assert docs[0].metadata == {"title": "Refund policy"}


async def test_local_explicit_streaming_overrides_kwargs():
    """Explicit streaming parameter must override streaming in load_kwargs for local connector."""
    fake_moss = FakeMossClient()
    mock_ds = _mock_load_dataset(SAMPLE_ROWS[:1])

    with (
        patch(
            "moss_connector_huggingface.connector.load_dataset", return_value=mock_ds
        ) as mock_load,
        patch("moss_connector_huggingface.ingest.MossClient", return_value=fake_moss),
    ):
        source = HuggingFaceLocalDatasetConnector(
            data_files=["train.parquet"],
            mapper=_simple_mapper,
            streaming=True,
        )
        source.load_kwargs["streaming"] = False
        list(source)

    mock_load.assert_called_once()
    _, call_kwargs = mock_load.call_args
    assert call_kwargs["streaming"] is True


