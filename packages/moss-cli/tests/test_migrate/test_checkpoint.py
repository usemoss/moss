"""Tests for the CheckpointStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from moss_cli.commands.migrate.checkpoint import CheckpointStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CheckpointStore:
    """Create a CheckpointStore that writes to a temp directory."""
    monkeypatch.chdir(tmp_path)
    return CheckpointStore("test-index")


class TestCheckpointStore:
    def test_path_format(self, store: CheckpointStore) -> None:
        assert store.path.name == ".moss-migrate-test-index.json"

    def test_path_sanitizes_slashes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        s = CheckpointStore("my/index")
        assert s.path.name == ".moss-migrate-my_index.json"

    def test_load_returns_none_when_no_file(self, store: CheckpointStore) -> None:
        assert store.load() is None

    def test_save_and_load(self, store: CheckpointStore) -> None:
        store.save(batch_offset=5, total_migrated=500)
        result = store.load()
        assert result == (5, 500)

    def test_save_overwrites(self, store: CheckpointStore) -> None:
        store.save(batch_offset=1, total_migrated=100)
        store.save(batch_offset=3, total_migrated=300)
        result = store.load()
        assert result == (3, 300)

    def test_clear_removes_file(self, store: CheckpointStore) -> None:
        store.save(batch_offset=1, total_migrated=100)
        assert store.path.exists()
        store.clear()
        assert not store.path.exists()

    def test_clear_noop_when_no_file(self, store: CheckpointStore) -> None:
        store.clear()  # should not raise

    def test_load_returns_none_for_corrupt_file(
        self, store: CheckpointStore
    ) -> None:
        store.path.write_text("not json")
        assert store.load() is None

    def test_load_returns_none_for_missing_keys(
        self, store: CheckpointStore
    ) -> None:
        store.path.write_text(json.dumps({"batch_offset": 1}))
        assert store.load() is None

    def test_save_creates_valid_json(self, store: CheckpointStore) -> None:
        store.save(batch_offset=10, total_migrated=1000)
        data = json.loads(store.path.read_text())
        assert data["batch_offset"] == 10
        assert data["total_migrated"] == 1000
