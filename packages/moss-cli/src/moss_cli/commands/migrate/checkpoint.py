"""Checkpoint store for resumable migrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple


class CheckpointStore:
    """Persist migration progress to a local JSON file.

    File is named `.moss-migrate-<index>.json` in the current working directory.
    """

    def __init__(self, target_index: str) -> None:
        safe_name = target_index.replace("/", "_").replace("\\", "_")
        self._path = Path(f".moss-migrate-{safe_name}.json")

    @property
    def path(self) -> Path:
        return self._path

    def save(self, batch_offset: int, total_migrated: int) -> None:
        """Write current progress to disk."""
        data = {
            "batch_offset": batch_offset,
            "total_migrated": total_migrated,
        }
        self._path.write_text(json.dumps(data, indent=2))

    def load(self) -> Optional[Tuple[int, int]]:
        """Load progress from disk.

        Returns (batch_offset, total_migrated) or None if no checkpoint exists.
        """
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text())
            return (data["batch_offset"], data["total_migrated"])
        except (json.JSONDecodeError, KeyError):
            return None

    def clear(self) -> None:
        """Remove the checkpoint file."""
        if self._path.exists():
            self._path.unlink()
