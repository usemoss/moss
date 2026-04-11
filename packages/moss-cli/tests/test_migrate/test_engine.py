"""Tests for the MigrationEngine."""

from __future__ import annotations

import asyncio
from typing import Iterator, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from moss_cli.commands.migrate.adapters.base import (
    SourceAdapter,
    SourceDocument,
    SourcePreview,
)
from moss_cli.commands.migrate.checkpoint import CheckpointStore
from moss_cli.commands.migrate.engine import MigrationEngine, MigrationResult
from moss_cli.commands.migrate.sink import MossSink


# -- Fixtures ----------------------------------------------------------------


class FakeAdapter(SourceAdapter):
    """In-memory adapter for testing."""

    def __init__(self, docs: List[SourceDocument]) -> None:
        self._docs = docs
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def preview(self) -> SourcePreview:
        dims = None
        if self._docs and self._docs[0].embedding:
            dims = len(self._docs[0].embedding)
        return SourcePreview(
            doc_count=len(self._docs),
            dimensions=dims,
            metadata_fields=[],
        )

    def stream(self, batch_size: int = 1000) -> Iterator[List[SourceDocument]]:
        batch: List[SourceDocument] = []
        for doc in self._docs:
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def close(self) -> None:
        self.closed = True


def _make_docs(n: int) -> List[SourceDocument]:
    return [
        SourceDocument(id=f"doc-{i}", text=f"Text {i}")
        for i in range(n)
    ]


@pytest.fixture
def fake_adapter() -> FakeAdapter:
    return FakeAdapter(_make_docs(5))


@pytest.fixture
def mock_sink() -> MagicMock:
    sink = MagicMock(spec=MossSink)
    sink.ensure_index = AsyncMock()
    sink.write_batch = AsyncMock(return_value="job_001")
    return sink


@pytest.fixture
def checkpoint(tmp_path, monkeypatch) -> CheckpointStore:
    monkeypatch.chdir(tmp_path)
    return CheckpointStore("test-target")


# -- Tests -------------------------------------------------------------------


class TestMigrationEnginePreview:
    def test_preview_connects_and_returns(self, fake_adapter: FakeAdapter, mock_sink, checkpoint) -> None:
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        preview = engine.preview()
        assert fake_adapter.connected
        assert preview.doc_count == 5


class TestMigrationEngineRun:
    def test_dry_run_does_not_write(self, fake_adapter, mock_sink, checkpoint) -> None:
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=10, resume=False, dry_run=True, json_mode=True))
        assert result.migrated == 0
        assert result.batches == 0
        mock_sink.write_batch.assert_not_called()

    def test_full_migration(self, fake_adapter, mock_sink, checkpoint) -> None:
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=10, resume=False, dry_run=False, json_mode=True))
        assert result.migrated == 5
        assert result.batches == 1
        assert result.failed == 0
        assert len(result.job_ids) == 1
        mock_sink.ensure_index.assert_called_once()
        mock_sink.write_batch.assert_called_once()

    def test_multiple_batches(self, mock_sink, checkpoint) -> None:
        adapter = FakeAdapter(_make_docs(7))
        engine = MigrationEngine(source=adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=3, resume=False, dry_run=False, json_mode=True))
        assert result.migrated == 7
        assert result.batches == 3  # 3 + 3 + 1
        assert mock_sink.write_batch.call_count == 3

    def test_resume_skips_completed_batches(self, mock_sink, checkpoint) -> None:
        # Simulate checkpoint: 1 batch already done (3 docs)
        checkpoint.save(batch_offset=1, total_migrated=3)
        adapter = FakeAdapter(_make_docs(7))
        engine = MigrationEngine(source=adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=3, resume=True, dry_run=False, json_mode=True))
        # Should skip first batch and write remaining 2 batches
        assert result.migrated == 3 + 4  # 3 from checkpoint + 4 new
        assert mock_sink.write_batch.call_count == 2  # skipped 1, wrote 2
        assert result.resumed_from == 1

    def test_failed_batch_counted(self, fake_adapter, mock_sink, checkpoint) -> None:
        mock_sink.write_batch = AsyncMock(side_effect=RuntimeError("write failed"))
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=10, resume=False, dry_run=False, json_mode=True))
        assert result.failed == 5
        assert result.migrated == 0
        # Checkpoint should NOT be cleared on failure
        assert checkpoint.path.exists()

    def test_checkpoint_cleared_on_success(self, fake_adapter, mock_sink, checkpoint) -> None:
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        asyncio.run(engine.run(batch_size=10, resume=False, dry_run=False, json_mode=True))
        assert not checkpoint.path.exists()

    def test_source_closed_after_run(self, fake_adapter, mock_sink, checkpoint) -> None:
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        asyncio.run(engine.run(batch_size=10, resume=False, dry_run=False, json_mode=True))
        assert fake_adapter.closed

    def test_human_output_mode(self, fake_adapter, mock_sink, checkpoint) -> None:
        """Ensure json_mode=False runs without error (uses progress bar)."""
        engine = MigrationEngine(source=fake_adapter, sink=mock_sink, checkpoint=checkpoint)
        result = asyncio.run(engine.run(batch_size=10, resume=False, dry_run=False, json_mode=False))
        assert result.migrated == 5


class TestMigrationResult:
    def test_to_dict_basic(self) -> None:
        r = MigrationResult(
            source_doc_count=100,
            migrated=90,
            failed=10,
            batches=5,
            elapsed_seconds=1.234,
            job_ids=["j1", "j2"],
        )
        d = r.to_dict()
        assert d["source_doc_count"] == 100
        assert d["migrated"] == 90
        assert d["failed"] == 10
        assert d["elapsed_seconds"] == 1.23
        assert d["job_ids"] == ["j1", "j2"]
        assert "resumed_from_batch" not in d

    def test_to_dict_with_resume(self) -> None:
        r = MigrationResult(
            source_doc_count=100,
            migrated=50,
            failed=0,
            batches=3,
            elapsed_seconds=2.0,
            resumed_from=2,
        )
        d = r.to_dict()
        assert d["resumed_from_batch"] == 2
