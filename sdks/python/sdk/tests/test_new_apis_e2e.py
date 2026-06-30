"""
E2E integration tests for new SDK APIs:
  - MossClient.session()
  - MossClient.load_indexes() / unload_indexes()
  - MossClient.query_multi_index()
  - MossClient.create_index_from_files()
  - ParseFileInput

Requires MOSS_TEST_PROJECT_ID and MOSS_TEST_PROJECT_KEY in .env.
Run with:
    pytest tests/test_new_apis_e2e.py -v -s -m e2e
"""

from __future__ import annotations

import time

import pytest

from moss import (
    DocumentInfo,
    GetDocumentsOptions,
    MossClient,
    MutationOptions,
    ParseFileInput,
    QueryOptions,
)
from moss.client.session_index import SessionIndex

from .constants import (
    TEST_PROJECT_ID,
    TEST_PROJECT_KEY,
    TEST_MODEL_ID,
    generate_unique_index_name,
)


@pytest.fixture
def client():
    return MossClient(TEST_PROJECT_ID, TEST_PROJECT_KEY)


TURN_DOCS = [
    DocumentInfo(id="turn-1", text="Customer was charged twice for the March renewal."),
    DocumentInfo(id="turn-2", text="Agent confirmed a refund for the duplicate charge."),
    DocumentInfo(id="turn-3", text="Customer also asked to cancel auto-renew."),
    DocumentInfo(id="turn-4", text="Agent placed a cancellation request for auto-renew."),
]

PRODUCT_DOCS = [
    DocumentInfo(id="p1", text="Sony WH-1000XM5 wireless headphones, 30-hour battery.", metadata={"category": "electronics"}),
    DocumentInfo(id="p2", text="Bose QuietComfort Ultra over-ear headphones with ANC.", metadata={"category": "electronics"}),
    DocumentInfo(id="p3", text="Apple AirPods Max with spatial audio and H1 chip.", metadata={"category": "electronics"}),
]

REVIEW_DOCS = [
    DocumentInfo(id="r1", text="Battery lasts a full transatlantic week easily.", metadata={"stars": "5"}),
    DocumentInfo(id="r2", text="Comfortable but noise cancelling could be stronger.", metadata={"stars": "4"}),
    DocumentInfo(id="r3", text="Sound quality incredible but battery degrades after a year.", metadata={"stars": "3"}),
]


# ---------------------------------------------------------------------------
# SessionIndex
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestSessionE2E:
    @pytest.mark.asyncio
    async def test_session_full_lifecycle(self, client):
        """
        Create a fresh session, add docs, query, delete a doc,
        retrieve by ID, push to cloud, then clean up.
        """
        index_name = generate_unique_index_name("e2e-session")

        try:
            # Open a new (empty) session
            session = await client.session(index_name)
            assert isinstance(session, SessionIndex)
            assert session.name == index_name
            assert session.doc_count == 0

            # Add documents
            added, updated = await session.add_docs(TURN_DOCS)
            assert added == len(TURN_DOCS)
            assert updated == 0
            assert session.doc_count == len(TURN_DOCS)

            # Query in-memory
            results = await session.query(
                "what did the customer want refunded",
                QueryOptions(top_k=3),
            )
            assert len(results.docs) > 0
            assert all(hasattr(d, "score") for d in results.docs)
            print(f"\n  session query returned {len(results.docs)} docs")

            # get_docs — all
            all_docs = await session.get_docs()
            assert len(all_docs) == len(TURN_DOCS)

            # get_docs — specific IDs
            specific = await session.get_docs(GetDocumentsOptions(doc_ids=["turn-1", "turn-2"]))
            assert len(specific) == 2
            ids = {d.id for d in specific}
            assert ids == {"turn-1", "turn-2"}

            # delete_docs
            deleted = await session.delete_docs(["turn-4"])
            assert deleted == 1
            assert session.doc_count == len(TURN_DOCS) - 1

            # Confirm deleted doc is gone
            after_delete = await session.get_docs(GetDocumentsOptions(doc_ids=["turn-4"]))
            assert len(after_delete) == 0

            # Push to cloud
            t0 = time.perf_counter()
            pushed = await session.push_index()
            elapsed = time.perf_counter() - t0
            assert pushed.job_id
            assert pushed.index_name == index_name
            assert pushed.doc_count == len(TURN_DOCS) - 1
            print(f"\n  session push: {elapsed:.1f}s, job={pushed.job_id}, status={pushed.status}")

        finally:
            try:
                await client.delete_index(index_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_session_upsert_updates_existing_doc(self, client):
        """Upserting a doc with the same ID should increment updated, not added."""
        index_name = generate_unique_index_name("e2e-session-upsert")

        try:
            session = await client.session(index_name)
            await session.add_docs([DocumentInfo(id="doc-1", text="original text")])
            assert session.doc_count == 1

            added, updated = await session.add_docs(
                [DocumentInfo(id="doc-1", text="updated text")],
                MutationOptions(upsert=True),
            )
            assert added == 0
            assert updated == 1
            assert session.doc_count == 1

        finally:
            try:
                await client.delete_index(index_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_session_resumes_existing_cloud_index(self, client):
        """Opening a session for an already-pushed index loads existing docs."""
        index_name = generate_unique_index_name("e2e-session-resume")

        try:
            # First session — push to cloud
            session1 = await client.session(index_name)
            await session1.add_docs(TURN_DOCS[:2])
            await session1.push_index()

            # Second session — should resume with existing doc count
            session2 = await client.session(index_name)
            assert session2.doc_count == 2

        finally:
            try:
                await client.delete_index(index_name)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# load_indexes / unload_indexes / query_multi_index
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestMultiIndexE2E:
    @pytest.mark.asyncio
    async def test_load_indexes_and_query_multi_index(self, client):
        """
        Create two indexes, bulk-load them, query across both,
        then bulk-unload and clean up.
        """
        ts = generate_unique_index_name("e2e-multi")
        products_idx = f"{ts}-products"
        reviews_idx = f"{ts}-reviews"

        try:
            # Create both indexes
            await client.create_index(products_idx, PRODUCT_DOCS, TEST_MODEL_ID)
            await client.create_index(reviews_idx, REVIEW_DOCS, TEST_MODEL_ID)

            # Bulk-load
            load_result = await client.load_indexes([products_idx, reviews_idx])
            assert products_idx in load_result.loaded
            assert reviews_idx in load_result.loaded
            assert isinstance(load_result.failed, dict)
            assert len(load_result.failed) == 0
            print(f"\n  loaded: {load_result.loaded}")

            # Multi-index query — global top-K across both
            results = await client.query_multi_index(
                load_result.loaded,
                "wireless headphones battery life",
                QueryOptions(top_k=5),
            )
            assert len(results.docs) > 0
            # Each result must carry its source index name
            for doc in results.docs:
                assert doc.index_name in (products_idx, reviews_idx)
            print(f"\n  multi-index query: {len(results.docs)} docs across {len(load_result.loaded)} indexes")

            # Bulk-unload
            await client.unload_indexes(load_result.loaded)

        finally:
            for name in (products_idx, reviews_idx):
                try:
                    await client.delete_index(name)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_load_indexes_partial_failure(self, client):
        """
        A non-existent name in load_indexes should appear in failed,
        not raise an exception.
        """
        real_idx = generate_unique_index_name("e2e-multi-partial")

        try:
            await client.create_index(real_idx, PRODUCT_DOCS, TEST_MODEL_ID)

            load_result = await client.load_indexes([real_idx, "does-not-exist-xyz"])
            assert real_idx in load_result.loaded
            assert "does-not-exist-xyz" in load_result.failed
            print(f"\n  partial load — loaded: {load_result.loaded}, failed: {load_result.failed}")

            await client.unload_indexes(load_result.loaded)

        finally:
            try:
                await client.delete_index(real_idx)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_unload_indexes_idempotent(self, client):
        """Unloading indexes that aren't loaded should not raise."""
        await client.unload_indexes(["not-loaded-a", "not-loaded-b"])

    @pytest.mark.asyncio
    async def test_query_multi_index_empty_names_raises(self, client):
        with pytest.raises(ValueError, match="at least one index name"):
            await client.query_multi_index([], "query")


# ---------------------------------------------------------------------------
# ParseFileInput + create_index_from_files
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestCreateIndexFromFilesE2E:
    @pytest.mark.asyncio
    async def test_create_index_from_files_custom_model_raises(self, client):
        """create_index_from_files must reject model_id='custom' before hitting the server."""
        with pytest.raises(ValueError, match="custom"):
            await client.create_index_from_files(
                "irrelevant",
                [ParseFileInput(name="f.pdf", content_type="application/pdf", data=b"%PDF-1.4")],
                model_id="custom",
            )


class TestParseFileInput:
    def test_path_only(self):
        f = ParseFileInput(name="doc.pdf", content_type="application/pdf", path="/tmp/doc.pdf")
        assert f.name == "doc.pdf"
        assert f.content_type == "application/pdf"
        assert f.path == "/tmp/doc.pdf"
        assert f.data is None

    def test_data_only(self):
        raw = b"%PDF-1.4 ..."
        f = ParseFileInput(name="doc.pdf", content_type="application/pdf", data=raw)
        assert f.data == raw
        assert f.path is None

    def test_defaults_are_none(self):
        f = ParseFileInput(name="x.pdf", content_type="application/pdf")
        assert f.path is None
        assert f.data is None
