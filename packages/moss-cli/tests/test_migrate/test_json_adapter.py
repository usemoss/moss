"""Tests for the JSON/JSONL file source adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from moss_cli.commands.migrate.adapters.json_file import JsonFileAdapter
from moss_cli.errors import CliValidationError


@pytest.fixture
def tmp_json_file(tmp_path: Path) -> Path:
    """Create a temp JSON file with sample documents."""
    docs = [
        {"id": "d1", "text": "Hello world", "metadata": {"tag": "greeting"}},
        {"id": "d2", "text": "Foo bar", "embedding": [0.1, 0.2, 0.3]},
        {"id": "d3", "text": "Baz qux"},
    ]
    f = tmp_path / "data.json"
    f.write_text(json.dumps(docs))
    return f


@pytest.fixture
def tmp_jsonl_file(tmp_path: Path) -> Path:
    """Create a temp JSONL file with sample documents."""
    lines = [
        json.dumps({"id": "l1", "text": "Line one", "metadata": {"src": "a"}}),
        json.dumps({"id": "l2", "text": "Line two"}),
        json.dumps({"text": "No ID here"}),
    ]
    f = tmp_path / "data.jsonl"
    f.write_text("\n".join(lines) + "\n")
    return f


@pytest.fixture
def tmp_json_wrapped(tmp_path: Path) -> Path:
    """Create a temp JSON file with docs nested under 'documents' key."""
    payload = {
        "documents": [
            {"id": "w1", "text": "Wrapped doc one"},
            {"id": "w2", "text": "Wrapped doc two"},
        ]
    }
    f = tmp_path / "wrapped.json"
    f.write_text(json.dumps(payload))
    return f


class TestJsonFileAdapterConnect:
    def test_connect_file_not_found(self, tmp_path: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_path / "missing.json"))
        with pytest.raises(CliValidationError, match="File not found"):
            adapter.connect()

    def test_connect_invalid_json(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{not valid json")
        adapter = JsonFileAdapter(str(f))
        with pytest.raises(CliValidationError, match="Invalid JSON"):
            adapter.connect()

    def test_connect_valid_json(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()  # should not raise

    def test_connect_valid_jsonl(self, tmp_jsonl_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_jsonl_file))
        adapter.connect()


class TestJsonFileAdapterPreview:
    def test_preview_counts(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        preview = adapter.preview()
        assert preview.doc_count == 3

    def test_preview_dimensions(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        preview = adapter.preview()
        assert preview.dimensions == 3  # from doc d2

    def test_preview_metadata_fields(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        preview = adapter.preview()
        assert "tag" in preview.metadata_fields

    def test_preview_no_embeddings(self, tmp_jsonl_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_jsonl_file))
        adapter.connect()
        preview = adapter.preview()
        assert preview.dimensions is None

    def test_preview_wrapped_docs(self, tmp_json_wrapped: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_wrapped))
        adapter.connect()
        preview = adapter.preview()
        assert preview.doc_count == 2


class TestJsonFileAdapterStream:
    def test_stream_single_batch(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        batches = list(adapter.stream(batch_size=100))
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_stream_multiple_batches(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        batches = list(adapter.stream(batch_size=2))
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_stream_doc_fields(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        batches = list(adapter.stream(batch_size=100))
        docs = batches[0]
        d1 = docs[0]
        assert d1.id == "d1"
        assert d1.text == "Hello world"
        assert d1.metadata == {"tag": "greeting"}
        assert d1.embedding is None

        d2 = docs[1]
        assert d2.id == "d2"
        assert d2.embedding == [0.1, 0.2, 0.3]

    def test_stream_auto_generates_id(self, tmp_jsonl_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_jsonl_file))
        adapter.connect()
        batches = list(adapter.stream(batch_size=100))
        docs = batches[0]
        # Third doc has no id, should get a UUID
        assert docs[2].id  # not empty
        assert docs[2].id != "l1"
        assert docs[2].id != "l2"

    def test_stream_jsonl(self, tmp_jsonl_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_jsonl_file))
        adapter.connect()
        batches = list(adapter.stream(batch_size=100))
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_stream_missing_text_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "no_text.json"
        f.write_text(json.dumps([{"id": "bad"}]))
        adapter = JsonFileAdapter(str(f))
        adapter.connect()
        with pytest.raises(CliValidationError, match="missing required 'text' field"):
            list(adapter.stream())


class TestJsonFileAdapterClose:
    def test_close_clears_docs(self, tmp_json_file: Path) -> None:
        adapter = JsonFileAdapter(str(tmp_json_file))
        adapter.connect()
        assert adapter._docs  # has data
        adapter.close()
        assert not adapter._docs  # cleared
