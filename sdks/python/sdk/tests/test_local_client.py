"""Unit tests for MossClient local mode."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from moss import MossClient


# -- Constructor (local) ------------------------------------------------


class TestLocalConstructor:
    def test_creates_local_client_without_credentials(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager") as mock_mgr_cls:
            c = MossClient.local(storage_path=str(tmp_path))

        assert c._local is True
        assert c._project_id == ""
        assert c._project_key == ""
        assert c._manage is None
        mock_mgr_cls.local.assert_called_once_with(str(tmp_path))

    def test_default_ttl_is_24_hours(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager"):
            c = MossClient.local(storage_path=str(tmp_path))
        assert c._ttl_hours == 24

    def test_custom_ttl(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager"):
            c = MossClient.local(storage_path=str(tmp_path), ttl_hours=0)
        assert c._ttl_hours == 0

    def test_storage_path_stored(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager"):
            c = MossClient.local(storage_path=str(tmp_path))
        assert c._storage_path == str(tmp_path)


# -- Create Index (local) -----------------------------------------------


class TestLocalCreateIndex:
    @pytest.mark.asyncio
    async def test_calls_create_local_index_and_save(self, local_client, tmp_path):
        mock_info = MagicMock()
        local_client._manager.create_local_index = MagicMock(return_value=mock_info)
        local_client._manager.save_index = MagicMock()

        docs = [MagicMock(embedding=None)]
        result = await local_client.create_index("my-idx", docs)

        local_client._manager.create_local_index.assert_called_once_with(
            "my-idx", docs, "moss-minilm"
        )
        local_client._manager.save_index.assert_called_once_with("my-idx")
        assert result == mock_info

    @pytest.mark.asyncio
    async def test_writes_meta_json(self, local_client, tmp_path):
        local_client._manager.create_local_index = MagicMock(return_value=MagicMock())
        local_client._manager.save_index = MagicMock()

        docs = [MagicMock(embedding=None)]
        await local_client.create_index("my-idx", docs)

        meta_path = tmp_path / "my-idx" / "meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert "last_accessed_at" in meta

    @pytest.mark.asyncio
    async def test_resolves_custom_model_for_embedded_docs(self, local_client):
        local_client._manager.create_local_index = MagicMock(return_value=MagicMock())
        local_client._manager.save_index = MagicMock()

        docs = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        await local_client.create_index("my-idx", docs)

        local_client._manager.create_local_index.assert_called_once_with(
            "my-idx", docs, "custom"
        )

    @pytest.mark.asyncio
    async def test_explicit_model_id_passed_through(self, local_client):
        local_client._manager.create_local_index = MagicMock(return_value=MagicMock())
        local_client._manager.save_index = MagicMock()

        docs = [MagicMock(embedding=None)]
        await local_client.create_index("my-idx", docs, model_id="moss-mediumlm")

        local_client._manager.create_local_index.assert_called_once_with(
            "my-idx", docs, "moss-mediumlm"
        )


# -- Load Index (local) -------------------------------------------------


class TestLocalLoadIndex:
    @pytest.mark.asyncio
    async def test_calls_load_local_index(self, local_client, tmp_path):
        local_client._manager.load_local_index = MagicMock()
        # Create meta so touch_meta works
        idx_dir = tmp_path / "my-idx"
        idx_dir.mkdir()
        (idx_dir / "meta.json").write_text(json.dumps({"last_accessed_at": 0}))

        result = await local_client.load_index("my-idx")

        assert result == "my-idx"
        local_client._manager.load_local_index.assert_called_once_with("my-idx")

    @pytest.mark.asyncio
    async def test_updates_last_accessed_at(self, local_client, tmp_path):
        local_client._manager.load_local_index = MagicMock()
        idx_dir = tmp_path / "my-idx"
        idx_dir.mkdir()
        old_time = time.time() - 3600
        (idx_dir / "meta.json").write_text(
            json.dumps({"last_accessed_at": old_time})
        )

        await local_client.load_index("my-idx")

        meta = json.loads((idx_dir / "meta.json").read_text())
        assert meta["last_accessed_at"] > old_time

    @pytest.mark.asyncio
    async def test_wraps_runtime_error(self, local_client):
        local_client._manager.load_local_index = MagicMock(
            side_effect=RuntimeError("not found on disk")
        )

        with pytest.raises(RuntimeError, match="Failed to load index 'bad'"):
            await local_client.load_index("bad")

    @pytest.mark.asyncio
    async def test_ignores_auto_refresh_in_local_mode(self, local_client, tmp_path):
        """auto_refresh and polling_interval are cloud-only; local mode ignores them."""
        local_client._manager.load_local_index = MagicMock()
        idx_dir = tmp_path / "my-idx"
        idx_dir.mkdir()
        (idx_dir / "meta.json").write_text(json.dumps({"last_accessed_at": 0}))

        result = await local_client.load_index(
            "my-idx", auto_refresh=True, polling_interval_in_seconds=30
        )
        assert result == "my-idx"
        local_client._manager.load_local_index.assert_called_once_with("my-idx")


# -- Query (local) ------------------------------------------------------


class TestLocalQuery:
    @pytest.mark.asyncio
    async def test_query_uses_local_path(self, local_client, tmp_path):
        mock_result = MagicMock()
        local_client._manager.query_text = MagicMock(return_value=mock_result)
        # Create meta for touch
        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        (idx_dir / "meta.json").write_text(json.dumps({"last_accessed_at": 0}))

        result = await local_client.query("idx", "search text")

        assert result == mock_result
        local_client._manager.query_text.assert_called_once_with(
            "idx", "search text", 5, 0.8, None
        )

    @pytest.mark.asyncio
    async def test_auto_loads_unloaded_index(self, local_client, tmp_path):
        """If index isn't in memory, local mode should auto-load from disk."""
        local_client._manager.has_index = MagicMock(
            side_effect=[False, True]  # not loaded, then loaded after load_index
        )
        local_client._manager.load_local_index = MagicMock()
        mock_result = MagicMock()
        local_client._manager.query_text = MagicMock(return_value=mock_result)

        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        (idx_dir / "meta.json").write_text(json.dumps({"last_accessed_at": 0}))

        result = await local_client.query("idx", "test")

        assert result == mock_result
        local_client._manager.load_local_index.assert_called_once_with("idx")

    @pytest.mark.asyncio
    async def test_query_with_custom_embedding(self, local_client, tmp_path):
        mock_result = MagicMock()
        local_client._manager.query = MagicMock(return_value=mock_result)
        idx_dir = tmp_path / "idx"
        idx_dir.mkdir()
        (idx_dir / "meta.json").write_text(json.dumps({"last_accessed_at": 0}))

        opts = MagicMock()
        opts.top_k = 3
        opts.alpha = 0.9
        opts.embedding = [0.1, 0.2]
        opts.filter = None

        result = await local_client.query("idx", "q", opts)

        assert result == mock_result
        local_client._manager.query.assert_called_once_with(
            "idx", "q", [0.1, 0.2], 3, 0.9, None
        )


# -- Delete Index (local) -----------------------------------------------


class TestLocalDeleteIndex:
    @pytest.mark.asyncio
    async def test_removes_directory(self, local_client, tmp_path):
        local_client._manager.unload_index = MagicMock()
        idx_dir = tmp_path / "my-idx"
        idx_dir.mkdir()
        (idx_dir / "index.bin").write_bytes(b"data")

        result = await local_client.delete_index("my-idx")

        assert result is True
        assert not idx_dir.exists()
        local_client._manager.unload_index.assert_called_once_with("my-idx")

    @pytest.mark.asyncio
    async def test_returns_false_for_missing_index(self, local_client):
        local_client._manager.unload_index = MagicMock(
            side_effect=RuntimeError("not loaded")
        )
        result = await local_client.delete_index("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_still_deletes_if_unload_fails(self, local_client, tmp_path):
        local_client._manager.unload_index = MagicMock(
            side_effect=RuntimeError("not loaded")
        )
        idx_dir = tmp_path / "my-idx"
        idx_dir.mkdir()
        (idx_dir / "index.bin").write_bytes(b"data")

        result = await local_client.delete_index("my-idx")

        assert result is True
        assert not idx_dir.exists()


# -- Get / List Indexes (local) -----------------------------------------


class TestLocalReadOps:
    @pytest.mark.asyncio
    async def test_get_index_calls_get_local_index_info(self, local_client):
        mock_info = MagicMock()
        local_client._manager.get_local_index_info = MagicMock(
            return_value=mock_info
        )

        result = await local_client.get_index("my-idx")

        assert result == mock_info
        local_client._manager.get_local_index_info.assert_called_once_with("my-idx")

    @pytest.mark.asyncio
    async def test_list_indexes_scans_storage(self, local_client, tmp_path):
        mock_info1 = MagicMock()
        mock_info2 = MagicMock()
        local_client._manager.get_local_index_info = MagicMock(
            side_effect=[mock_info1, mock_info2]
        )

        # Create two index directories with index.bin
        for name in ["idx-a", "idx-b"]:
            d = tmp_path / name
            d.mkdir()
            (d / "index.bin").write_bytes(b"data")

        # Create a non-index directory (no index.bin)
        (tmp_path / "not-an-index").mkdir()

        result = await local_client.list_indexes()

        assert len(result) == 2
        assert mock_info1 in result
        assert mock_info2 in result

    @pytest.mark.asyncio
    async def test_list_indexes_returns_empty_when_no_storage(self, local_client):
        local_client._storage_path = "/nonexistent/path"
        result = await local_client.list_indexes()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_indexes_skips_corrupted(self, local_client, tmp_path):
        local_client._manager.get_local_index_info = MagicMock(
            side_effect=RuntimeError("corrupted")
        )
        d = tmp_path / "bad-idx"
        d.mkdir()
        (d / "index.bin").write_bytes(b"corrupt")

        result = await local_client.list_indexes()
        assert result == []


# -- NotImplementedError for cloud-only ops ----------------------------


class TestLocalNotImplemented:
    @pytest.mark.asyncio
    async def test_add_docs_raises(self, local_client):
        with pytest.raises(NotImplementedError, match="create_index to rebuild"):
            await local_client.add_docs("idx", [MagicMock()])

    @pytest.mark.asyncio
    async def test_delete_docs_raises(self, local_client):
        with pytest.raises(NotImplementedError, match="create_index to rebuild"):
            await local_client.delete_docs("idx", ["doc-1"])

    @pytest.mark.asyncio
    async def test_get_docs_raises(self, local_client):
        with pytest.raises(NotImplementedError, match="not available in local mode"):
            await local_client.get_docs("idx")

    @pytest.mark.asyncio
    async def test_get_job_status_raises(self, local_client):
        with pytest.raises(NotImplementedError, match="not available in local mode"):
            await local_client.get_job_status("job-123")


# -- TTL / Cleanup -----------------------------------------------------


class TestTTLCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_indexes(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager") as mock_mgr_cls:
            mock_manager = mock_mgr_cls.local.return_value
            mock_manager.unload_index = MagicMock()

            c = MossClient.local(storage_path=str(tmp_path), ttl_hours=1)
            c._manager = mock_manager
            c._cleanup_done = True

            # Create an expired index
            expired_dir = tmp_path / "old-idx"
            expired_dir.mkdir()
            (expired_dir / "index.bin").write_bytes(b"data")
            (expired_dir / "meta.json").write_text(
                json.dumps({"last_accessed_at": time.time() - 7200})  # 2h ago
            )

            # Create a fresh index
            fresh_dir = tmp_path / "new-idx"
            fresh_dir.mkdir()
            (fresh_dir / "index.bin").write_bytes(b"data")
            (fresh_dir / "meta.json").write_text(
                json.dumps({"last_accessed_at": time.time()})
            )

            deleted = await c.cleanup()

            assert deleted == 1
            assert not expired_dir.exists()
            assert fresh_dir.exists()

    @pytest.mark.asyncio
    async def test_cleanup_noop_when_ttl_zero(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager") as mock_mgr_cls:
            c = MossClient.local(storage_path=str(tmp_path), ttl_hours=0)
            c._manager = mock_mgr_cls.local.return_value
            c._cleanup_done = True

            # Create an old index
            old_dir = tmp_path / "old-idx"
            old_dir.mkdir()
            (old_dir / "meta.json").write_text(
                json.dumps({"last_accessed_at": 0})
            )

            deleted = await c.cleanup()
            assert deleted == 0
            assert old_dir.exists()

    @pytest.mark.asyncio
    async def test_lazy_cleanup_runs_on_first_op(self, tmp_path):
        with patch("moss.client.moss_client.IndexManager") as mock_mgr_cls:
            mock_manager = mock_mgr_cls.local.return_value
            mock_manager.has_index = MagicMock(return_value=True)
            mock_manager.query_text = MagicMock(return_value=MagicMock())
            mock_manager.unload_index = MagicMock()

            c = MossClient.local(storage_path=str(tmp_path), ttl_hours=1)
            c._manager = mock_manager
            # _cleanup_done is False by default

            # Create an expired index
            expired_dir = tmp_path / "expired"
            expired_dir.mkdir()
            (expired_dir / "index.bin").write_bytes(b"data")
            (expired_dir / "meta.json").write_text(
                json.dumps({"last_accessed_at": time.time() - 7200})
            )

            # Create the target index dir for meta touch
            target_dir = tmp_path / "idx"
            target_dir.mkdir()
            (target_dir / "meta.json").write_text(
                json.dumps({"last_accessed_at": time.time()})
            )

            # First query triggers cleanup
            await c.query("idx", "test")

            assert not expired_dir.exists()
            assert c._cleanup_done is True

    @pytest.mark.asyncio
    async def test_cleanup_noop_in_cloud_mode(self):
        with (
            patch("moss.client.moss_client.ManageClient"),
            patch("moss.client.moss_client.IndexManager"),
        ):
            c = MossClient("pid", "pkey")
            deleted = await c.cleanup()
            assert deleted == 0
