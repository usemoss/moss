"""Unit tests for MossClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from moss.client.moss_client import MossClient


# -- Fixtures ----------------------------------------------------------

@pytest.fixture
def client():
    with patch("moss.client.moss_client.ManageClient") as mock_manage, \
         patch("moss.client.moss_client.IndexManager") as mock_mgr:
        c = MossClient("test-project", "test-key")
        c._manage = mock_manage.return_value
        c._manager = mock_mgr.return_value
        # Default: index is loaded locally (local query path)
        c._manager.has_index = MagicMock(return_value=True)
        yield c


@pytest.fixture
def raw_mocks():
    """Yields (mock_manage_cls, mock_mgr_cls) so tests can inspect constructor args."""
    with patch("moss.client.moss_client.ManageClient") as mock_manage, \
         patch("moss.client.moss_client.IndexManager") as mock_mgr:
        yield mock_manage, mock_mgr


# -- Constructor -------------------------------------------------------

class TestConstructor:
    def test_manage_client_created_with_manage_url(self, raw_mocks):
        mock_manage_cls, mock_mgr_cls = raw_mocks
        MossClient("pid", "pkey")

        mock_manage_cls.assert_called_once()
        args = mock_manage_cls.call_args[0]
        assert args[0] == "pid"
        assert args[1] == "pkey"
        assert "/v1/manage" in args[2]

    def test_index_manager_created_with_manage_url(self, raw_mocks):
        mock_manage_cls, mock_mgr_cls = raw_mocks
        MossClient("pid", "pkey")

        mock_mgr_cls.assert_called_once()
        args = mock_mgr_cls.call_args[0]
        assert args[0] == "pid"
        assert args[1] == "pkey"
        assert "/v1/manage" in args[2]


# -- Model ID Resolution ----------------------------------------------

class TestModelIdResolution:
    def test_explicit_model_id(self, client):
        docs = [MagicMock(embedding=None)]
        assert client._resolve_model_id(docs, "custom") == "custom"

    def test_default_model_when_no_embeddings(self, client):
        docs = [MagicMock(embedding=None)]
        assert client._resolve_model_id(docs, None) == "moss-minilm"

    def test_custom_when_embeddings_present(self, client):
        docs = [MagicMock(embedding=[1.0, 2.0])]
        assert client._resolve_model_id(docs, None) == "custom"

    def test_explicit_model_overrides_embeddings(self, client):
        docs = [MagicMock(embedding=[1.0, 2.0])]
        assert client._resolve_model_id(docs, "moss-minilm") == "moss-minilm"

    def test_empty_docs_defaults_to_moss_minilm(self, client):
        assert client._resolve_model_id([], None) == "moss-minilm"

    def test_mixed_embeddings_detects_as_custom(self, client):
        docs = [MagicMock(embedding=[1.0]), MagicMock(embedding=None)]
        assert client._resolve_model_id(docs, None) == "custom"

    def test_large_doc_list_resolution(self, client):
        docs = [MagicMock(embedding=None) for _ in range(10_000)]
        assert client._resolve_model_id(docs, None) == "moss-minilm"

    def test_large_doc_list_with_embeddings(self, client):
        docs = [MagicMock(embedding=[0.1] * 384) for _ in range(10_000)]
        assert client._resolve_model_id(docs, None) == "custom"


# -- Create Index ------------------------------------------------------

class TestCreateIndex:
    @pytest.mark.asyncio
    async def test_delegates_to_manage_client(self, client):
        mock_result = MagicMock(job_id="j1", index_name="idx", doc_count=2)
        client._manage.create_index = MagicMock(return_value=mock_result)

        docs = [MagicMock(embedding=None)]
        result = await client.create_index("idx", docs, "moss-minilm")

        assert result.job_id == "j1"
        client._manage.create_index.assert_called_once_with("idx", docs, "moss-minilm")

    @pytest.mark.asyncio
    async def test_resolves_model_id_when_none(self, client):
        mock_result = MagicMock()
        client._manage.create_index = MagicMock(return_value=mock_result)

        docs = [MagicMock(embedding=None)]
        await client.create_index("idx", docs)

        client._manage.create_index.assert_called_once_with("idx", docs, "moss-minilm")

    @pytest.mark.asyncio
    async def test_propagates_rust_error(self, client):
        client._manage.create_index = MagicMock(side_effect=RuntimeError("upload failed"))

        with pytest.raises(RuntimeError, match="upload failed"):
            await client.create_index("idx", [MagicMock(embedding=None)])

    @pytest.mark.asyncio
    async def test_with_large_doc_list(self, client):
        mock_result = MagicMock(job_id="j-large", index_name="big", doc_count=50_000)
        client._manage.create_index = MagicMock(return_value=mock_result)

        docs = [MagicMock(embedding=None) for _ in range(50_000)]
        result = await client.create_index("big", docs, "moss-minilm")

        assert result.doc_count == 50_000
        assert result.job_id == "j-large"

    @pytest.mark.asyncio
    async def test_auto_resolves_custom_for_embedded_docs(self, client):
        mock_result = MagicMock()
        client._manage.create_index = MagicMock(return_value=mock_result)

        docs = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        await client.create_index("idx", docs)

        client._manage.create_index.assert_called_once_with("idx", docs, "custom")


# -- Add Docs ---------------------------------------------------------

class TestAddDocs:
    @pytest.mark.asyncio
    async def test_delegates_to_manage_client(self, client):
        mock_result = MagicMock()
        client._manage.add_docs = MagicMock(return_value=mock_result)

        docs = [MagicMock()]
        result = await client.add_docs("idx", docs)

        assert result == mock_result
        client._manage.add_docs.assert_called_once_with("idx", docs, None)

    @pytest.mark.asyncio
    async def test_passes_mutation_options(self, client):
        mock_result = MagicMock()
        client._manage.add_docs = MagicMock(return_value=mock_result)

        opts = MagicMock(upsert=True)
        docs = [MagicMock()]
        await client.add_docs("idx", docs, options=opts)

        client._manage.add_docs.assert_called_once_with("idx", docs, opts)

    @pytest.mark.asyncio
    async def test_propagates_rust_error(self, client):
        client._manage.add_docs = MagicMock(side_effect=RuntimeError("job failed"))

        with pytest.raises(RuntimeError, match="job failed"):
            await client.add_docs("idx", [MagicMock()])

    @pytest.mark.asyncio
    async def test_empty_docs_list(self, client):
        mock_result = MagicMock(doc_count=0)
        client._manage.add_docs = MagicMock(return_value=mock_result)

        result = await client.add_docs("idx", [])
        assert result.doc_count == 0

    @pytest.mark.asyncio
    async def test_large_batch(self, client):
        mock_result = MagicMock(doc_count=10_000)
        client._manage.add_docs = MagicMock(return_value=mock_result)

        docs = [MagicMock() for _ in range(10_000)]
        result = await client.add_docs("idx", docs)

        assert result.doc_count == 10_000


# -- Delete Docs -------------------------------------------------------

class TestDeleteDocs:
    @pytest.mark.asyncio
    async def test_delegates_to_manage_client(self, client):
        mock_result = MagicMock()
        client._manage.delete_docs = MagicMock(return_value=mock_result)

        result = await client.delete_docs("idx", ["doc-1", "doc-2"])

        assert result == mock_result
        client._manage.delete_docs.assert_called_once_with("idx", ["doc-1", "doc-2"])

    @pytest.mark.asyncio
    async def test_empty_doc_ids(self, client):
        mock_result = MagicMock(doc_count=0)
        client._manage.delete_docs = MagicMock(return_value=mock_result)

        result = await client.delete_docs("idx", [])
        assert result.doc_count == 0

    @pytest.mark.asyncio
    async def test_propagates_rust_error(self, client):
        client._manage.delete_docs = MagicMock(side_effect=RuntimeError("index not found"))

        with pytest.raises(RuntimeError, match="index not found"):
            await client.delete_docs("idx", ["doc-1"])

    @pytest.mark.asyncio
    async def test_large_delete_batch(self, client):
        mock_result = MagicMock(doc_count=5_000)
        client._manage.delete_docs = MagicMock(return_value=mock_result)

        ids = [f"doc-{i}" for i in range(5_000)]
        result = await client.delete_docs("idx", ids)

        assert result.doc_count == 5_000


# -- Read Operations ---------------------------------------------------

class TestReadOps:
    @pytest.mark.asyncio
    async def test_get_index(self, client):
        mock_info = MagicMock()
        client._manage.get_index = MagicMock(return_value=mock_info)

        result = await client.get_index("idx")
        assert result == mock_info

    @pytest.mark.asyncio
    async def test_list_indexes(self, client):
        client._manage.list_indexes = MagicMock(return_value=[])

        result = await client.list_indexes()
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_index(self, client):
        client._manage.delete_index = MagicMock(return_value=True)

        result = await client.delete_index("idx")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_docs(self, client):
        from moss import GetDocumentsOptions

        client._manage.get_docs = MagicMock(return_value=[])
        opts = GetDocumentsOptions(doc_ids=["doc-1"])

        result = await client.get_docs("idx", opts)
        assert result == []
        client._manage.get_docs.assert_called_once_with("idx", opts)

    @pytest.mark.asyncio
    async def test_get_docs_without_options(self, client):
        client._manage.get_docs = MagicMock(return_value=[MagicMock(), MagicMock()])

        result = await client.get_docs("idx")
        assert len(result) == 2
        client._manage.get_docs.assert_called_once_with("idx", None)

    @pytest.mark.asyncio
    async def test_get_job_status(self, client):
        mock_status = MagicMock()
        client._manage.get_job_status = MagicMock(return_value=mock_status)

        result = await client.get_job_status("job-123")
        assert result == mock_status

    @pytest.mark.asyncio
    async def test_get_index_propagates_error(self, client):
        client._manage.get_index = MagicMock(side_effect=RuntimeError("not found"))

        with pytest.raises(RuntimeError, match="not found"):
            await client.get_index("nonexistent")


# -- Load Index --------------------------------------------------------

class TestLoadIndex:
    @pytest.mark.asyncio
    async def test_delegates_to_index_manager(self, client):
        mock_info = MagicMock()
        client._manager.load_index = MagicMock(return_value=mock_info)
        client._manager.load_query_model = MagicMock(return_value=None)

        result = await client.load_index("idx")

        assert result == "idx"
        client._manager.load_index.assert_called_once_with("idx", False, 600)
        client._manager.load_query_model.assert_called_once_with("idx")

    @pytest.mark.asyncio
    async def test_with_auto_refresh(self, client):
        mock_info = MagicMock()
        client._manager.load_index = MagicMock(return_value=mock_info)
        client._manager.load_query_model = MagicMock(return_value=None)

        await client.load_index("idx", auto_refresh=True, polling_interval_in_seconds=120)

        client._manager.load_index.assert_called_once_with("idx", True, 120)
        client._manager.load_query_model.assert_called_once_with("idx")

    @pytest.mark.asyncio
    async def test_wraps_runtime_error(self, client):
        client._manager.load_index = MagicMock(side_effect=RuntimeError("download failed"))

        with pytest.raises(RuntimeError, match="Failed to load index 'idx'"):
            await client.load_index("idx")

    @pytest.mark.asyncio
    async def test_warms_query_model_after_load(self, client):
        mock_info = MagicMock()
        client._manager.load_index = MagicMock(return_value=mock_info)
        client._manager.load_query_model = MagicMock(return_value=None)

        await client.load_index("idx")

        client._manager.load_query_model.assert_called_once_with("idx")


# -- Query (local path) ------------------------------------------------

class TestQueryLocal:
    @pytest.mark.asyncio
    async def test_query_with_custom_embedding(self, client):
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = 3
        opts.alpha = 0.9
        opts.embedding = [0.1, 0.2, 0.3]
        opts.filter = None

        result = await client.query("idx", "search text", opts)

        assert result == mock_result
        client._manager.query.assert_called_once_with(
            "idx", "search text", [0.1, 0.2, 0.3], 3, 0.9, None,
        )

    @pytest.mark.asyncio
    async def test_query_defaults_top_k_and_alpha(self, client):
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = None
        opts.alpha = None
        opts.embedding = [0.5]
        opts.filter = None

        await client.query("idx", "q", opts)

        client._manager.query.assert_called_once_with("idx", "q", [0.5], 5, 0.8, None)

    @pytest.mark.asyncio
    async def test_query_raises_for_custom_model_without_embedding(self, client):
        client._manager.query_text = MagicMock(
            side_effect=RuntimeError("Index model 'custom' requires explicit query embeddings.")
        )

        opts = MagicMock()
        opts.embedding = None
        opts.top_k = 5
        opts.alpha = 0.8

        with pytest.raises(ValueError, match="custom embeddings"):
            await client.query("idx", "q", opts)

    @pytest.mark.asyncio
    async def test_query_no_options_uses_defaults(self, client):
        client._manager.query_text = MagicMock(
            side_effect=RuntimeError("Index model 'custom' requires explicit query embeddings.")
        )

        with pytest.raises(ValueError, match="custom embeddings"):
            await client.query("idx", "q")

    @pytest.mark.asyncio
    async def test_query_passes_filter_to_manager(self, client):
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = 5
        opts.alpha = 0.8
        opts.embedding = [0.1]

        metadata_filter = {"field": "city", "condition": {"$eq": "NYC"}}
        opts.filter = metadata_filter
        result = await client.query("idx", "q", opts)

        assert result == mock_result
        client._manager.query.assert_called_once_with(
            "idx", "q", [0.1], 5, 0.8, metadata_filter,
        )

    @pytest.mark.asyncio
    async def test_query_passes_none_filter_when_omitted(self, client):
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = 5
        opts.alpha = 0.8
        opts.embedding = [0.1]
        opts.filter = None

        await client.query("idx", "q", opts)

        client._manager.query.assert_called_once_with(
            "idx", "q", [0.1], 5, 0.8, None,
        )

    @pytest.mark.asyncio
    async def test_query_passes_complex_and_filter(self, client):
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = 10
        opts.alpha = 0.8
        opts.embedding = [0.5]

        metadata_filter = {"$and": [
            {"field": "city", "condition": {"$eq": "NYC"}},
            {"field": "price", "condition": {"$lt": "50"}},
        ]}
        opts.filter = metadata_filter
        await client.query("idx", "q", opts)

        client._manager.query.assert_called_once_with(
            "idx", "q", [0.5], 10, 0.8, metadata_filter,
        )

    @pytest.mark.asyncio
    async def test_query_uses_rust_query_text_when_embedding_omitted(self, client):
        mock_result = MagicMock()
        client._manager.query_text = MagicMock(return_value=mock_result)

        result = await client.query("idx", "search")

        assert result == mock_result
        client._manager.query_text.assert_called_once_with("idx", "search", 5, 0.8, None)


# -- Query (cloud fallback) --------------------------------------------

class TestQueryCloudFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_cloud_when_index_not_loaded(self, client):
        client._manager.has_index = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "docs": [{"id": "d1", "text": "hello", "score": 0.9}],
            "query": "test",
            "indexName": "idx",
            "timeTakenMs": 42,
        }

        with patch("moss.client.moss_client.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.query("idx", "test")

        assert len(result.docs) == 1
        assert result.docs[0].id == "d1"
        assert result.docs[0].score == pytest.approx(0.9, abs=1e-6)

    @pytest.mark.asyncio
    async def test_cloud_fallback_uses_query_url(self, client):
        client._manager.has_index = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {"docs": [], "query": "q"}

        with patch("moss.client.moss_client.httpx.AsyncClient") as mock_httpx:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.query("idx", "q")

            call_args = mock_client_instance.post.call_args
            url = call_args[0][0]
            assert "/query" in url
            assert "/manage" not in url

    @pytest.mark.asyncio
    async def test_uses_local_when_index_loaded(self, client):
        """When index is loaded, should NOT hit cloud."""
        client._manager.has_index = MagicMock(return_value=True)
        mock_result = MagicMock()
        client._manager.query = MagicMock(return_value=mock_result)

        opts = MagicMock()
        opts.top_k = 5
        opts.alpha = 0.8
        opts.embedding = [0.1]

        result = await client.query("idx", "q", opts)

        assert result == mock_result
        client._manager.query.assert_called_once()

