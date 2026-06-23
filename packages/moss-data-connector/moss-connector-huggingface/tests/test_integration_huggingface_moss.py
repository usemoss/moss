"""End-to-end integration test: HuggingFace Dataset → Moss.

Loads a small public HuggingFace dataset (ag_news, 4-class news classification),
ingests it into a live Moss project via ``ingest()``, runs a real semantic
query, and cleans everything up on exit.

SKIPPED unless both MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set.

Run with:
    pytest tests/test_integration_huggingface_moss.py -v -s

Environment variables (set in .env or the shell):
    MOSS_PROJECT_ID   — required
    MOSS_PROJECT_KEY  — required
    HF_TOKEN          — optional; only needed for gated/private datasets
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for _candidate in (
        _here.parents[1] / ".env",
        _here.parents[2] / ".env",
        _here.parents[4] / ".env",
    ):
        if _candidate.exists():
            load_dotenv(_candidate, override=False)
            break
except ImportError:
    pass

pytest.importorskip("datasets")

from moss import DocumentInfo, MossClient, QueryOptions  # noqa: E402
from moss_connector_huggingface import HuggingFaceDatasetConnector, ingest  # noqa: E402

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # optional for public datasets

pytestmark = pytest.mark.skipif(
    not (PROJECT_ID and PROJECT_KEY),
    reason="Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY to run this live test.",
)

# We use a 20-row slice of ag_news so the test stays fast and free.
DATASET = "ag_news"
SPLIT = "test[:20]"

# ag_news label map: 0=World, 1=Sports, 2=Business, 3=Sci/Tech
LABEL_MAP = {0: "World", 1: "Sports", 2: "Business", 3: "Sci/Tech"}


def _ag_news_mapper(row: dict[str, Any]) -> DocumentInfo:
    return DocumentInfo(
        id=str(row["label"]) + "-" + str(uuid.uuid4().hex[:6]),
        text=row["text"],
        metadata={"category": LABEL_MAP[row["label"]]},
    )


async def test_huggingface_hub_ingest_to_moss():
    """Full round trip: HuggingFace ag_news → ingest() → Moss → query → delete."""
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-hf-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = HuggingFaceDatasetConnector(
            dataset_name=DATASET,
            mapper=_ag_news_mapper,
            split=SPLIT,
            streaming=False,  # small slice, no need to stream
            token=HF_TOKEN,
        )

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        assert result.doc_count == 20

        await client.load_index(index_name)
        query_result = await client.query(
            index_name, "technology and software news", QueryOptions(top_k=3)
        )

        assert query_result.docs, "expected at least one result"
        # ag_news Sci/Tech articles (label 3) should rank highly for this query
        categories = [(doc.metadata or {}).get("category") for doc in query_result.docs]
        print(f"\nTop 3 results for 'technology and software news': {categories}")
        assert any(cat in ("Sci/Tech", "Business") for cat in categories)

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to delete index {index_name}: {exc}")


async def test_huggingface_filter_fn_live():
    """filter_fn should restrict ingestion to matching rows only."""
    client = MossClient(PROJECT_ID, PROJECT_KEY)
    index_name = f"moss-hf-filter-e2e-{uuid.uuid4().hex[:8]}"

    try:
        source = HuggingFaceDatasetConnector(
            dataset_name=DATASET,
            mapper=_ag_news_mapper,
            split=SPLIT,
            streaming=False,
            filter_fn=lambda row: row["label"] == 1,  # Sports only
            token=HF_TOKEN,
        )

        result = await ingest(source, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None
        # All ingested docs should be Sports category
        assert result.doc_count > 0

        await client.load_index(index_name)
        query_result = await client.query(
            index_name, "football match results", QueryOptions(top_k=3)
        )
        categories = [(doc.metadata or {}).get("category") for doc in query_result.docs]
        print(f"\nSports-only index top results: {categories}")
        assert all(cat == "Sports" for cat in categories)

    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to delete index {index_name}: {exc}")
