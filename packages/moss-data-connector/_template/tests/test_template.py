"""Template unit test. Rename to test_<source>.py and adapt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest  # noqa: F401

from moss import DocumentInfo  # noqa: F401

# TODO: update these imports to match your renamed package.
# from moss_connector_<source> import <Source>Connector, ingest


@dataclass
class FakeMossClient:
    """Records create_index calls without hitting the network."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        self.calls.append({"name": name, "docs": list(docs), "model_id": model_id})


# Example test, adapt to your source. See moss-connector-sqlite/tests/test_sqlite.py
# for a worked example that uses a real stdlib driver + fake MossClient.
#
# async def test_<source>_ingest():
#     fake_moss = FakeMossClient()
#     with patch("moss_connector_<source>.ingest.MossClient", return_value=fake_moss):
#         source = <Source>Connector(..., mapper=lambda r: DocumentInfo(...))
#         count = await ingest(source, "fake_id", "fake_key", "idx")
#     assert count == ...
