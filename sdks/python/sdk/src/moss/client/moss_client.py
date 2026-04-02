from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx
from moss_core import (
    CLOUD_API_MANAGE_URL,
    ManageClient,
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    IndexManager,
    MutationOptions,
    MutationResult,
    JobStatusResponse,
    QueryOptions,
    QueryResultDocumentInfo,
    SearchResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_STORAGE_PATH = os.path.join(os.path.expanduser("~"), ".moss", "indexes")
_DEFAULT_TTL_HOURS = 24


def _get_manage_url() -> str:
    """Manage URL, overridable via env for local development."""
    return os.getenv("MOSS_CLOUD_API_MANAGE_URL", CLOUD_API_MANAGE_URL)


def _get_query_url() -> str:
    """Query URL, derived from manage URL or overridable via env."""
    explicit = os.getenv("MOSS_CLOUD_QUERY_URL")
    if explicit:
        return explicit
    return _get_manage_url().replace("/v1/manage", "/query")


class MossClient:
    """
    Semantic search client for vector similarity operations.

    **Cloud mode** (default):
        All mutations and reads go through the Rust ManageClient.
        Querying uses the local IndexManager when the index is loaded,
        otherwise falls back to the cloud query API.

    **Local mode** (via ``MossClient.local()``):
        All operations run entirely on-device — no API keys, no cloud.
        Indexes are persisted to disk and managed with an optional TTL.

    Example (cloud):
        ```python
        from moss import MossClient, DocumentInfo

        client = MossClient("project-id", "project-key")

        docs = [DocumentInfo(id="1", text="Machine learning fundamentals")]
        result = await client.create_index("my-index", docs, "moss-minilm")

        await client.load_index("my-index")
        results = await client.query("my-index", "AI and neural networks")
        ```

    Example (local):
        ```python
        from moss import MossClient, DocumentInfo, QueryOptions

        client = MossClient.local()

        docs = [DocumentInfo(id="1", text="Machine learning fundamentals")]
        await client.create_index("my-index", docs)

        await client.load_index("my-index")
        results = await client.query("my-index", "AI", QueryOptions(top_k=5))
        ```
    """

    DEFAULT_MODEL_ID = "moss-minilm"

    def __init__(self, project_id: str, project_key: str) -> None:
        self._project_id = project_id
        self._project_key = project_key
        self._client_id = str(uuid.uuid4())
        self._local = False
        self._storage_path: Optional[str] = None
        self._ttl_hours: int = _DEFAULT_TTL_HOURS
        self._cleanup_done = False
        manage_url = _get_manage_url()
        self._manage = ManageClient(
            project_id, project_key, manage_url, self._client_id
        )
        self._manager = IndexManager(
            project_id, project_key, manage_url, self._client_id
        )

    @classmethod
    def local(
        cls,
        storage_path: str = _DEFAULT_STORAGE_PATH,
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> "MossClient":
        """
        Create a fully local MossClient — no API keys, no cloud.

        Indexes are persisted to ``storage_path`` and automatically cleaned
        up after ``ttl_hours`` of inactivity. Set ``ttl_hours=0`` to disable
        expiry (durable storage mode).

        Args:
            storage_path: Root directory for local index storage.
            ttl_hours: Hours of inactivity before an index is deleted.
                       0 disables automatic cleanup.
        """
        instance = cls.__new__(cls)
        instance._project_id = ""
        instance._project_key = ""
        instance._client_id = str(uuid.uuid4())
        instance._local = True
        instance._storage_path = storage_path
        instance._ttl_hours = ttl_hours
        instance._cleanup_done = False
        instance._manage = None  # type: ignore[assignment]
        instance._manager = IndexManager.local(storage_path)
        return instance

    # -- Mutations (via Rust ManageClient) --------------------------

    async def create_index(
        self,
        name: str,
        docs: List[DocumentInfo],
        model_id: Optional[str] = None,
    ) -> Union[MutationResult, IndexInfo]:
        """Create a new index and populate it with documents.

        Returns:
            Cloud mode: ``MutationResult`` with ``job_id``, ``index_name``, ``doc_count``.
            Local mode: ``IndexInfo`` with index metadata (no job — build is synchronous).
        """
        if self._local:
            await self._maybe_cleanup()
            resolved_model_id = self._resolve_model_id(docs, model_id)
            info = await asyncio.to_thread(
                self._manager.create_local_index,
                name,
                docs,
                resolved_model_id,
            )
            await asyncio.to_thread(self._manager.save_index, name)
            await asyncio.to_thread(self._write_meta, name)
            return info

        resolved_model_id = self._resolve_model_id(docs, model_id)
        return await asyncio.to_thread(
            self._manage.create_index,
            name,
            docs,
            resolved_model_id,
        )

    async def add_docs(
        self,
        name: str,
        docs: List[DocumentInfo],
        options: Optional[MutationOptions] = None,
    ) -> MutationResult:
        """Add or update documents in an index."""
        if self._local:
            raise NotImplementedError(
                "Use create_index to rebuild. Incremental mutations coming in v2."
            )
        return await asyncio.to_thread(
            self._manage.add_docs,
            name,
            docs,
            options,
        )

    async def delete_docs(
        self,
        name: str,
        doc_ids: List[str],
    ) -> MutationResult:
        """Delete documents from an index by their IDs."""
        if self._local:
            raise NotImplementedError(
                "Use create_index to rebuild. Incremental mutations coming in v2."
            )
        return await asyncio.to_thread(
            self._manage.delete_docs,
            name,
            doc_ids,
        )

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        """Get the status of a bulk operation job."""
        if self._local:
            raise NotImplementedError("Job status is not available in local mode.")
        return await asyncio.to_thread(self._manage.get_job_status, job_id)

    # -- Read operations (via Rust ManageClient) --------------------

    async def get_index(self, name: str) -> IndexInfo:
        """Get information about a specific index."""
        if self._local:
            return await asyncio.to_thread(
                self._manager.get_local_index_info, name
            )
        return await asyncio.to_thread(self._manage.get_index, name)

    async def list_indexes(self) -> List[IndexInfo]:
        """List all indexes with their information."""
        if self._local:
            return await self._list_local_indexes()
        return await asyncio.to_thread(self._manage.list_indexes)

    async def delete_index(self, name: str) -> bool:
        """Delete an index and all its data."""
        if self._local:
            return await self._delete_local_index(name)
        return await asyncio.to_thread(self._manage.delete_index, name)

    async def get_docs(
        self,
        name: str,
        options: Optional[GetDocumentsOptions] = None,
    ) -> List[DocumentInfo]:
        """Retrieve documents from an index."""
        if self._local:
            raise NotImplementedError(
                "Document retrieval is not available in local mode."
            )
        return await asyncio.to_thread(self._manage.get_docs, name, options)

    # -- Index loading & querying -----------------------------------

    async def load_index(
        self,
        name: str,
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> str:
        """
        Load an index into memory for fast local querying.

        In cloud mode, downloads from the cloud API.
        In local mode, loads from disk (``load_local_index`` handles both
        index loading and query model warming in a single call).

        Without load_index(), query() falls back to the cloud API (~100-500ms).
        With load_index(), queries run entirely in-memory (~1-10ms).
        """
        if self._local:
            await self._maybe_cleanup()
            try:
                await asyncio.to_thread(
                    self._manager.load_local_index, name
                )
                await asyncio.to_thread(self._touch_meta, name)
                return name
            except RuntimeError as e:
                raise RuntimeError(f"Failed to load index '{name}': {e}") from e

        try:
            await asyncio.to_thread(
                self._manager.load_index,
                name,
                auto_refresh,
                polling_interval_in_seconds,
            )
            await asyncio.to_thread(self._manager.load_query_model, name)
            return name
        except RuntimeError as e:
            raise RuntimeError(f"Failed to load index '{name}': {e}") from e

    async def unload_index(self, name: str) -> None:
        """Unload an index from memory."""
        try:
            await asyncio.to_thread(self._manager.unload_index, name)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to unload index '{name}': {e}") from e

    async def query(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult:
        """
        Perform a semantic similarity search.

        If the index is loaded locally (via load_index), queries run in-memory.
        Otherwise, falls back to the cloud query API (cloud mode) or
        auto-loads from disk (local mode).

        Args:
            options: Query options (top_k, alpha, embedding, filter). Example filter:
                QueryOptions(filter={"$and": [
                    {"field": "city", "condition": {"$eq": "NYC"}},
                    {"field": "price", "condition": {"$lt": "50"}},
                ]})
        """
        if self._local:
            await self._maybe_cleanup()

        is_loaded = await asyncio.to_thread(self._manager.has_index, name)

        if not is_loaded and self._local:
            await self.load_index(name)
            is_loaded = True

        if is_loaded:
            if self._local:
                await asyncio.to_thread(self._touch_meta, name)
            return await self._query_local(name, query, options)

        if getattr(options, "filter", None) is not None:
            logger.warning(
                "Metadata filter ignored: filtering is only supported for locally loaded indexes. "
                "Call load_index('%s') first.",
                name,
            )
        return await self._query_cloud(name, query, options)

    # -- Internal ---------------------------------------------------

    async def _query_local(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions],
    ) -> SearchResult:
        top_k = getattr(options, "top_k", None)
        if top_k is None:
            top_k = 5
        alpha = getattr(options, "alpha", None)
        if alpha is None:
            alpha = 0.8
        query_embedding = getattr(options, "embedding", None)
        filter = getattr(options, "filter", None)

        if query_embedding is None:
            try:
                return await asyncio.to_thread(
                    self._manager.query_text,
                    name,
                    query,
                    top_k,
                    alpha,
                    filter,
                )
            except RuntimeError as e:
                if "requires explicit query embeddings" in str(e):
                    raise ValueError(
                        "This index uses custom embeddings. "
                        "Query embeddings must be provided via QueryOptions.embedding."
                    ) from e
                raise

        return await asyncio.to_thread(
            self._manager.query,
            name,
            query,
            list(query_embedding),
            top_k,
            alpha,
            filter,
        )

    async def _query_cloud(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions],
    ) -> SearchResult:
        """Fallback: query via the cloud API when the index is not loaded locally."""
        top_k = getattr(options, "top_k", None) or 10
        query_embedding = getattr(options, "embedding", None)

        request_body: Dict[str, Any] = {
            "query": query,
            "indexName": name,
            "projectId": self._project_id,
            "projectKey": self._project_key,
            "topK": top_k,
        }
        if query_embedding is not None:
            request_body["queryEmbedding"] = list(query_embedding)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    _get_query_url(),
                    headers={"Content-Type": "application/json"},
                    json=request_body,
                )
                if not response.is_success:
                    raise Exception(f"HTTP error! status: {response.status_code}")
                data = response.json()
        except httpx.RequestError as error:
            raise Exception(f"Cloud query request failed: {str(error)}")

        return self._dict_to_search_result(data)

    @staticmethod
    def _dict_to_search_result(data: dict) -> SearchResult:
        docs = [
            QueryResultDocumentInfo(
                id=d.get("id", ""),
                text=d.get("text", ""),
                metadata=d.get("metadata"),
                score=float(d.get("score", 0.0)),
            )
            for d in data.get("docs", [])
        ]
        return SearchResult(
            docs=docs,
            query=data.get("query", ""),
            index_name=data.get("indexName"),
            time_taken_ms=data.get("timeTakenMs"),
        )

    def _resolve_model_id(
        self,
        docs: List[DocumentInfo],
        model_id: Optional[str],
    ) -> str:
        if model_id is not None:
            return model_id
        has_embeddings = any(
            getattr(doc, "embedding", None) is not None for doc in docs
        )
        return "custom" if has_embeddings else self.DEFAULT_MODEL_ID

    # -- Local mode helpers --------------------------------------------

    def _index_dir(self, name: str) -> Path:
        """Return the on-disk directory for a local index."""
        assert self._storage_path is not None
        return Path(self._storage_path) / name

    def _meta_path(self, name: str) -> Path:
        return self._index_dir(name) / "meta.json"

    def _write_meta(self, name: str) -> None:
        """Write a fresh meta.json with current timestamp."""
        meta = {"last_accessed_at": time.time()}
        path = self._meta_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta))

    def _touch_meta(self, name: str) -> None:
        """Update last_accessed_at in meta.json if it exists."""
        path = self._meta_path(name)
        if path.exists():
            try:
                meta = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                meta = {}
            meta["last_accessed_at"] = time.time()
            path.write_text(json.dumps(meta))

    async def _delete_local_index(self, name: str) -> bool:
        """Unload from memory and remove from disk."""
        try:
            await asyncio.to_thread(self._manager.unload_index, name)
        except Exception:
            pass
        index_dir = self._index_dir(name)
        if index_dir.exists():
            await asyncio.to_thread(shutil.rmtree, str(index_dir))
            return True
        return False

    async def _list_local_indexes(self) -> List[IndexInfo]:
        """Scan the storage directory for persisted indexes."""
        assert self._storage_path is not None
        storage = Path(self._storage_path)
        if not storage.exists():
            return []
        results: List[IndexInfo] = []
        for child in sorted(storage.iterdir(), key=lambda p: p.name):
            if child.is_dir() and (child / "index.bin").exists():
                try:
                    info = await asyncio.to_thread(
                        self._manager.get_local_index_info, child.name
                    )
                    results.append(info)
                except Exception:
                    logger.warning("Skipping corrupted index: %s", child.name)
        return results

    async def cleanup(self) -> int:
        """
        Delete local indexes that have exceeded their TTL.

        Returns the number of indexes deleted. Does nothing if ``ttl_hours``
        is 0 (durable storage mode).
        """
        if not self._local or self._ttl_hours == 0:
            return 0
        assert self._storage_path is not None
        storage = Path(self._storage_path)
        if not storage.exists():
            return 0

        deleted = 0
        cutoff = time.time() - (self._ttl_hours * 3600)

        for child in storage.iterdir():
            if not child.is_dir():
                continue
            meta_path = child / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
                last_accessed = meta.get("last_accessed_at", 0)
            except (json.JSONDecodeError, OSError):
                continue
            if last_accessed < cutoff:
                try:
                    await asyncio.to_thread(
                        self._manager.unload_index, child.name
                    )
                except Exception:
                    pass
                await asyncio.to_thread(shutil.rmtree, str(child))
                deleted += 1
                logger.info("TTL cleanup: deleted index '%s'", child.name)

        return deleted

    async def _maybe_cleanup(self) -> None:
        """Run TTL cleanup lazily on the first async operation."""
        if self._cleanup_done or not self._local:
            return
        self._cleanup_done = True
        await self.cleanup()
