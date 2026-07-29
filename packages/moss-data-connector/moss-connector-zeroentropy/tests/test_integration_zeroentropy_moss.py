from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("zeroentropy")

from moss import MossClient, QueryOptions  # noqa: E402
from moss_connector_zeroentropy import ZeroEntropyConnector, ingest  # noqa: E402

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for candidate in (
        _here.parents[1] / ".env",
        _here.parents[2] / ".env",
        _here.parents[4] / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)
except ImportError:
    pass

ZE_API_KEY = os.getenv("ZEROENTROPY_API_KEY")
ZE_COLLECTION = os.getenv("ZEROENTROPY_TEST_COLLECTION")
PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (ZE_API_KEY and ZE_COLLECTION and PROJECT_ID and PROJECT_KEY),
    reason=(
        "Set ZEROENTROPY_API_KEY, ZEROENTROPY_TEST_COLLECTION (a pre-populated "
        "ZeroEntropy collection), MOSS_PROJECT_ID, and MOSS_PROJECT_KEY to run."
    ),
)


async def test_zeroentropy_migration_end_to_end():
    """Full round trip: ZeroEntropy collection -> Moss index -> query -> delete."""
    index_name = f"moss-zeroentropy-e2e-{uuid.uuid4().hex[:8]}"
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    try:
        connector = ZeroEntropyConnector(
            collection_name=ZE_COLLECTION,
            api_key=ZE_API_KEY,
        )

        result = await ingest(connector, PROJECT_ID, PROJECT_KEY, index_name=index_name)
        assert result is not None, "no documents migrated from the ZeroEntropy collection"
        assert result.doc_count >= 1

        await client.load_index(index_name)
        query = await client.query(index_name, "test", QueryOptions(top_k=3))
        assert query.docs, "expected at least one document back from the migrated index"
    finally:
        try:
            await client.delete_index(index_name)
        except Exception as exc:  # pragma: no cover - best-effort cleanup
            print(f"warning: failed to delete test index {index_name}: {exc}")
