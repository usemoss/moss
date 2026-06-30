from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from moss_core import (
    ManageClient,
    DocumentInfo,
    GetDocumentsOptions,
    IndexInfo,
    IndexManager,
    LoadIndexesResult,
    MutationOptions,
    MutationResult,
    JobStatusResponse,
    QueryOptions,
    QueryResultDocumentInfo,
    SearchResult,
)

from .session_index import SessionIndex

logger = logging.getLogger(__name__)

_DEFAULT_MANAGE_URL = "https://service.usemoss.dev/v1/manage"


def _get_manage_url() -> str:
    """Manage URL, overridable via env for staging/local/self-hosted setups."""
    return os.getenv("MOSS_CLOUD_API_MANAGE_URL", _DEFAULT_MANAGE_URL)


def _get_query_url() -> str:
    """
    Query URL resolution order:
      1. MOSS_CLOUD_QUERY_URL  (legacy name)
      2. MOSS_QUERY_URL        (shorter alias)
      3. Derived from manage URL by replacing /v1/manage → /query
         so staging and self-hosted setups get the right endpoint automatically.
    """
    explicit = os.getenv("MOSS_CLOUD_QUERY_URL") or os.getenv("MOSS_QUERY_URL")
    if explicit:
        return explicit
    return _get_manage_url().replace("/v1/manage", "/query")


@dataclass
class ParseFileInput:
    """
    Input descriptor for a single file in the parse pipeline.

    Either ``path`` (filesystem path) or ``data`` (raw bytes) must be provided.
    Both ``name`` and ``content_type`` are required. Only ``"application/pdf"``
    is currently supported as ``content_type``.
    """

    name: str
    content_type: str
    path: Optional[str] = None
    data: Optional[bytes] = None


class MossClient:
    """
    Semantic search client for vector similarity operations.

    All mutations and reads go through the Rust ManageClient.
    Querying uses the local IndexManager when the index is loaded,
    otherwise falls back to the cloud query API.

    Example:
        ```python
        from moss import MossClient, DocumentInfo

        client = MossClient("project-id", "project-key")

        docs = [DocumentInfo(id="1", text="Machine learning fundamentals")]
        result = await client.create_index("my-index", docs, "moss-minilm")

        await client.load_index("my-index")
        results = await client.query("my-index", "AI and neural networks")
        ```
    """

    DEFAULT_MODEL_ID = "moss-minilm"

    def __init__(self, project_id: str, project_key: str) -> None:
        self._project_id = project_id
        self._project_key = project_key
        self._client_id = str(uuid.uuid4())
        manage_url = _get_manage_url()
        self._manage = ManageClient(
            project_id, project_key, manage_url, self._client_id
        )
        self._manager = IndexManager(
            project_id, project_key, manage_url, self._client_id
        )

    # -- Mutations --------------------------------------------------

    async def create_index(
        self,
        name: str,
        docs: List[DocumentInfo],
        model_id: Optional[str] = None,
    ) -> MutationResult:
        """Create a new index and populate it with documents."""
        resolved_model_id = self._resolve_model_id(docs, model_id)
        return await asyncio.to_thread(
            self._manage.create_index,
            name,
            docs,
            resolved_model_id,
        )

    async def create_index_from_files(
        self,
        name: str,
        files: List[ParseFileInput],
        model_id: Optional[str] = None,
    ) -> MutationResult:
        """
        Create a new index by uploading raw files (PDFs) for server-side
        parsing and embedding. At most 20 files per call.

        Args:
            name: Name for the new index.
            files: List of ParseFileInput. Each requires ``name`` and
                   ``content_type``, plus at least one of ``path`` or ``data``.
            model_id: Embedding model. Defaults to 'moss-minilm'. 'custom' is
                      not supported (embeddings are generated server-side).

        Raises:
            ValueError: If model_id is 'custom'.
        """
        resolved = model_id or self.DEFAULT_MODEL_ID
        if resolved == "custom":
            raise ValueError(
                "create_index_from_files does not support model_id='custom' — "
                "the parse pipeline generates embeddings server-side. "
                "Use create_index() with pre-computed embeddings instead."
            )
        from moss_core import ParseFileInput as CoreParseFileInput

        core_files = [
            CoreParseFileInput(f.name, f.content_type, path=f.path, data=f.data)
            for f in files
        ]
        return await asyncio.to_thread(
            self._manage.create_index_from_files, name, core_files, resolved
        )

    async def add_docs(
        self,
        name: str,
        docs: List[DocumentInfo],
        options: Optional[MutationOptions] = None,
    ) -> MutationResult:
        """Add or update documents in an index."""
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
        return await asyncio.to_thread(
            self._manage.delete_docs,
            name,
            doc_ids,
        )

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        """Get the status of a bulk operation job."""
        return await asyncio.to_thread(self._manage.get_job_status, job_id)

    # -- Read operations --------------------------------------------

    async def get_index(self, name: str) -> IndexInfo:
        """Get information about a specific index."""
        return await asyncio.to_thread(self._manage.get_index, name)

    async def list_indexes(self) -> List[IndexInfo]:
        """List all indexes with their information."""
        return await asyncio.to_thread(self._manage.list_indexes)

    async def delete_index(self, name: str) -> bool:
        """Delete an index and all its data."""
        return await asyncio.to_thread(self._manage.delete_index, name)

    async def get_docs(
        self,
        name: str,
        options: Optional[GetDocumentsOptions] = None,
    ) -> List[DocumentInfo]:
        """Retrieve documents from an index."""
        return await asyncio.to_thread(self._manage.get_docs, name, options)

    # -- Index loading ----------------------------------------------

    async def load_index(
        self,
        name: str,
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> str:
        """
        Download an index from the cloud into memory for fast local querying.

        Without load_index(), query() falls back to the cloud API (~100-500ms).
        With load_index(), queries run entirely in-memory (~1-10ms).
        """
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

    async def load_indexes(
        self,
        names: List[str],
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
    ) -> LoadIndexesResult:
        """
        Bulk-load many indexes into memory. Best-effort: failures on individual
        names do not roll back successes. Returns a LoadIndexesResult with
        ``loaded`` (list of names) and ``failed`` (dict mapping name -> error).

        Mirrors load_index(): warms the query model for each successfully loaded
        index so text queries work without caller-supplied embeddings.
        """
        result = await asyncio.to_thread(
            self._manager.load_indexes,
            names,
            auto_refresh,
            polling_interval_in_seconds,
            None,
        )
        # Warm query models in parallel — load_query_model is idempotent so
        # indexes sharing a model only pay the cost once.
        warm_results = await asyncio.gather(
            *[
                asyncio.to_thread(self._manager.load_query_model, name)
                for name in result.loaded
            ],
            return_exceptions=True,
        )
        for name, exc in zip(result.loaded, warm_results):
            if isinstance(exc, Exception):
                logger.warning(
                    "Failed to warm query model for '%s' after bulk load: %s", name, exc
                )
        return result

    async def unload_indexes(self, names: List[str]) -> None:
        """Bulk-unload many indexes. Idempotent for names that aren't loaded."""
        await asyncio.to_thread(self._manager.unload_indexes, names)

    # -- Querying ---------------------------------------------------

    async def query(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult:
        """
        Perform a semantic similarity search.

        Queries run in-memory if the index is loaded via load_index(),
        otherwise falls back to the cloud query API.

        Args:
            options: Query options (top_k, alpha, embedding, filter). Example filter:
                QueryOptions(filter={"$and": [
                    {"field": "city", "condition": {"$eq": "NYC"}},
                    {"field": "price", "condition": {"$lt": "50"}},
                ]})
        """
        is_loaded = await asyncio.to_thread(self._manager.has_index, name)

        if is_loaded:
            return await self._query_local(name, query, options)

        if getattr(options, "filter", None) is not None:
            logger.warning(
                "Metadata filter ignored: filtering is only supported for locally loaded indexes. "
                "Call load_index('%s') first.",
                name,
            )
        return await self._query_cloud(name, query, options)

    async def query_multi_index(
        self,
        names: List[str],
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult:
        """
        Search across multiple loaded indexes and return the global top-K.

        All requested indexes must be loaded locally and share the same
        embedding model. Each result document is tagged with its source
        ``index_name``.

        Multi-index search is embedding-only — ``options.alpha`` is ignored
        (forced to 1.0) because BM25 IDF is per-corpus and not comparable
        across indexes.

        Args:
            names: Names of indexes to search; must be non-empty and all loaded.
            query: The query text.
            options: Query options (top_k, embedding, filter). ``alpha`` is ignored.
        """
        if not names:
            raise ValueError("query_multi_index requires at least one index name")

        top_k = getattr(options, "top_k", None) or 10
        query_embedding = getattr(options, "embedding", None)
        filter_ = getattr(options, "filter", None)

        if query_embedding is not None:
            return await asyncio.to_thread(
                self._manager.query_multi_index,
                names,
                query,
                list(query_embedding),
                top_k,
                filter_,
            )

        try:
            return await asyncio.to_thread(
                self._manager.query_multi_index_text,
                names,
                query,
                top_k,
                filter_,
            )
        except RuntimeError as e:
            if "requires explicit query embeddings" in str(e):
                raise ValueError(
                    "One or more indexes use custom embeddings. "
                    "Query embeddings must be provided via QueryOptions.embedding."
                ) from e
            raise

    # -- Sessions ---------------------------------------------------

    async def session(
        self,
        index_name: str,
        model_id: Optional[str] = None,
    ) -> SessionIndex:
        """
        Create or resume a local session index.

        If a cloud index with the given name already exists it is automatically
        loaded into the session; otherwise the session starts empty. The
        workflow is the same either way — add docs, query, push at the end.

        Args:
            index_name: Cloud index name used as the push target.
            model_id: Embedding model. Defaults to "moss-minilm".
                      Other options: "moss-mediumlm", "custom".

        Returns:
            SessionIndex: A local index ready to use.

        Raises:
            RuntimeError: If project credentials are invalid.
            ValueError: If an existing cloud index uses a different model than
                        the explicit model_id passed here.
        """
        resolved_model_id = model_id or self.DEFAULT_MODEL_ID

        sess = SessionIndex._create(
            name=index_name,
            model_id=resolved_model_id,
            project_id=self._project_id,
            project_key=self._project_key,
            client_id=self._client_id,
        )

        # Attempt to load an existing cloud index into the session.
        # not-found/404 → fresh session (loaded=False); auth/network errors propagate.
        loaded = False
        try:
            await asyncio.to_thread(sess._inner.load_index, index_name)
            loaded = True
        except RuntimeError as e:
            msg = str(e).lower()
            if "not found" not in msg and "404" not in msg:
                raise

        if loaded:
            # Always inspect the model regardless of doc count — an existing empty
            # cloud index still carries its original model, so gating on doc_count > 0
            # would silently convert a custom/moss-mediumlm index into a moss-minilm
            # session.
            loaded_model_id = sess._inner.model_id
            if loaded_model_id != resolved_model_id:
                if model_id is not None:
                    raise ValueError(
                        f"Existing session index '{index_name}' uses model_id='{loaded_model_id}', "
                        f"but session() was called with model_id='{resolved_model_id}'. "
                        "Omit model_id to adopt the stored model or pass the matching model_id."
                    )
                sess._model_id = loaded_model_id

        if sess._model_id != "custom":
            await sess._get_embedding_service()

        return sess

    # -- Internal ---------------------------------------------------

    async def _query_local(
        self,
        name: str,
        query: str,
        options: Optional[QueryOptions],
    ) -> SearchResult:
        top_k_raw = getattr(options, "top_k", None)
        top_k = 5 if top_k_raw is None else top_k_raw
        alpha_raw = getattr(options, "alpha", None)
        alpha = 0.8 if alpha_raw is None else alpha_raw
        query_embedding = getattr(options, "embedding", None)
        filter_ = getattr(options, "filter", None)

        if query_embedding is None:
            try:
                return await asyncio.to_thread(
                    self._manager.query_text,
                    name,
                    query,
                    top_k,
                    alpha,
                    filter_,
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
            filter_,
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
