"""Agno integration for the Moss in-memory semantic search runtime."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agno.knowledge.document import Document
from agno.utils.log import log_debug, log_error, log_info, log_warning
from agno.vectordb.base import VectorDb
from moss import (
    DocumentInfo,
    GetDocumentsOptions,
    MossClient,
    MutationOptions,
    QueryOptions,
)

__all__ = ["MossRuntime"]


class MossRuntime(VectorDb):
    """Agno knowledge source backed by the Moss in-memory semantic search runtime.

    Moss downloads your index and runs queries
    entirely in-process, giving sub-10ms retrieval with no embedder and no
    external infrastructure required.

    Call ``create()`` once at startup to load an existing index; subsequent
    ``search()`` calls run entirely in memory. On first ``upsert()``,
    the index is created automatically if it does not exist.

    Args:
        index_name: Name of the Moss index (equivalent to a collection).
        project_id: Moss project ID. Falls back to ``MOSS_PROJECT_ID`` env var.
        project_key: Moss project key. Falls back to ``MOSS_PROJECT_KEY`` env var.
        embedding_model: Moss embedding model — ``"moss-minilm"`` (default,
            faster) or ``"moss-mediumlm"`` (higher accuracy).
        alpha: Hybrid search weight — 1.0 = pure semantic, 0.0 = pure keyword.
            Defaults to 0.8.
        auto_refresh: Auto-refresh the loaded index when new docs are added.
        polling_interval_in_seconds: Interval for auto-refresh. Defaults to 600.
    """

    def __init__(
        self,
        index_name: str,
        project_id: str | None = None,
        project_key: str | None = None,
        embedding_model: str = "moss-minilm",
        alpha: float = 0.8,
        auto_refresh: bool = False,
        polling_interval_in_seconds: int = 600,
        name: str | None = None,
        description: str | None = None,
        id: str | None = None,
    ):
        """Initialize the MossRuntime."""
        self.index_name = index_name
        self.embedding_model = embedding_model
        self.alpha = alpha
        self.auto_refresh = auto_refresh
        self.polling_interval_in_seconds = polling_interval_in_seconds

        resolved_id = project_id or os.getenv("MOSS_PROJECT_ID") or ""
        resolved_key = project_key or os.getenv("MOSS_PROJECT_KEY") or ""

        if not resolved_id or not resolved_key:
            raise ValueError(
                "Moss credentials required. Provide project_id and project_key "
                "or set MOSS_PROJECT_ID and MOSS_PROJECT_KEY environment variables."
            )

        self._client: MossClient = MossClient(resolved_id, resolved_key)
        self._index_loaded: bool = False

        super().__init__(id=id, name=name or index_name, description=description)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, coro: Any) -> Any:
        """Run a coroutine from a sync context, even inside a running event loop.

        asyncio.run() raises RuntimeError when called inside a running loop
        (Jupyter, FastAPI async handlers). This detects that case and
        dispatches to a fresh thread instead.
        """
        try:
            asyncio.get_running_loop()
            in_running_loop = True
        except RuntimeError:
            in_running_loop = False

        if in_running_loop:
            with ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def _to_moss_doc(self, document: Document, content_hash: str | None = None) -> DocumentInfo:
        meta: dict[str, str] = {str(k): str(v) for k, v in (document.meta_data or {}).items()}
        if content_hash:
            meta["content_hash"] = content_hash
        if document.content_id:
            meta["content_id"] = document.content_id
        if document.name:
            meta["name"] = document.name
        return DocumentInfo(
            id=document.id or document.content_id or str(uuid.uuid4()),
            text=document.content,
            metadata=meta,
        )

    def _to_document(self, result: Any) -> Document:
        meta = dict(result.metadata) if result.metadata else {}
        if (score := getattr(result, "score", None)) is not None:
            meta["_score"] = str(score)
        return Document(
            id=result.id,
            content=result.text,
            meta_data=meta,
            name=meta.get("name"),
            content_id=meta.get("content_id"),
        )

    async def _load_index(self) -> None:
        if not self._index_loaded:
            log_debug(f"Loading Moss index '{self.index_name}' into memory")
            await self._client.load_index(
                self.index_name,
                auto_refresh=self.auto_refresh,
                polling_interval_in_seconds=self.polling_interval_in_seconds,
            )
            self._index_loaded = True

    async def _upsert_docs(self, moss_docs: list[DocumentInfo]) -> None:
        if not await self.async_exists():
            log_info(f"Creating Moss index '{self.index_name}' with model '{self.embedding_model}'")
            await self._client.create_index(self.index_name, moss_docs, self.embedding_model)
        else:
            await self._client.add_docs(
                self.index_name, moss_docs, options=MutationOptions(upsert=True)
            )
        self._index_loaded = False
        await self._load_index()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(self) -> None:
        """Load the index into memory if it already exists."""
        if self.exists():
            self._run(self._load_index())

    async def async_create(self) -> None:
        """Async variant of create()."""
        if await self.async_exists():
            await self._load_index()

    def drop(self) -> None:
        """Delete the Moss index and all its data."""
        try:
            self._run(self._client.delete_index(self.index_name))
            self._index_loaded = False
            log_info(f"Deleted Moss index '{self.index_name}'")
        except Exception as e:
            log_error(f"Error deleting Moss index '{self.index_name}': {e}")

    async def async_drop(self) -> None:
        """Async variant of drop()."""
        try:
            await self._client.delete_index(self.index_name)
            self._index_loaded = False
            log_info(f"Deleted Moss index '{self.index_name}'")
        except Exception as e:
            log_error(f"Error deleting Moss index '{self.index_name}': {e}")

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    def exists(self) -> bool:
        """Return True if the index exists in the project."""
        try:
            indexes = self._run(self._client.list_indexes())
            return any(idx.name == self.index_name for idx in indexes)
        except Exception:
            return False

    async def async_exists(self) -> bool:
        """Async variant of exists()."""
        try:
            indexes = await self._client.list_indexes()
            return any(idx.name == self.index_name for idx in indexes)
        except Exception:
            return False

    def name_exists(self, name: str) -> bool:
        """Return True if this VectorDb manages the given index name."""
        return name == self.index_name and self.exists()

    async def async_name_exists(self, name: str) -> bool:
        """Async variant of name_exists()."""
        return name == self.index_name and await self.async_exists()

    def id_exists(self, id: str) -> bool:
        """Return True if a document with the given ID exists in the index."""
        try:
            docs = self._run(
                self._client.get_docs(self.index_name, GetDocumentsOptions(doc_ids=[id]))
            )
            return bool(docs)
        except Exception:
            return False

    def content_hash_exists(self, content_hash: str) -> bool:
        """Return True if a document with the given content hash exists.

        Metadata filtering requires a locally loaded index. Returns False
        (safe: forces re-upsert) when the index is not yet loaded.
        """
        if not self._index_loaded:
            return False
        try:
            results = self._run(
                self._client.query(
                    self.index_name,
                    content_hash,
                    options=QueryOptions(
                        alpha=0.0,
                        top_k=1,
                        filter={"field": "content_hash", "condition": {"$eq": content_hash}},
                    ),
                )
            )
            return bool(results and results.docs)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Insert / Upsert
    # ------------------------------------------------------------------

    def upsert_available(self) -> bool:
        """Moss supports upsert natively."""
        return True

    def insert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: Any | None = None,
    ) -> None:
        """Insert documents; delegates to upsert."""
        self.upsert(content_hash=content_hash, documents=documents, filters=filters)

    async def async_insert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: Any | None = None,
    ) -> None:
        """Async variant of insert()."""
        await self.async_upsert(content_hash=content_hash, documents=documents, filters=filters)

    def upsert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: Any | None = None,
    ) -> None:
        """Upsert documents into the index, creating it if necessary."""
        moss_docs = [self._to_moss_doc(doc, content_hash) for doc in documents]
        if not moss_docs:
            return
        try:
            self._run(self._upsert_docs(moss_docs))
            log_info(f"Upserted {len(moss_docs)} documents into Moss index '{self.index_name}'")
        except Exception as e:
            log_error(f"Error upserting documents into Moss: {e}")

    async def async_upsert(
        self,
        content_hash: str,
        documents: list[Document],
        filters: Any | None = None,
    ) -> None:
        """Async variant of upsert()."""
        moss_docs = [self._to_moss_doc(doc, content_hash) for doc in documents]
        if not moss_docs:
            return
        try:
            await self._upsert_docs(moss_docs)
            log_info(f"Upserted {len(moss_docs)} documents into Moss index '{self.index_name}'")
        except Exception as e:
            log_error(f"Error upserting documents into Moss: {e}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 5, filters: Any | None = None) -> list[Document]:
        """Search the index and return the top matching documents."""
        try:
            results = self._run(
                self._client.query(
                    self.index_name,
                    query,
                    options=QueryOptions(top_k=limit, alpha=self.alpha, filter=filters),
                )
            )
            if not results or not results.docs:
                return []
            docs = [self._to_document(r) for r in results.docs]
            log_debug(f"Moss search returned {len(docs)} results for '{query}'")
            return docs
        except Exception as e:
            log_error(f"Error searching Moss index '{self.index_name}': {e}")
            return []

    async def async_search(
        self, query: str, limit: int = 5, filters: Any | None = None
    ) -> list[Document]:
        """Async variant of search()."""
        try:
            results = await self._client.query(
                self.index_name,
                query,
                options=QueryOptions(top_k=limit, alpha=self.alpha, filter=filters),
            )
            if not results or not results.docs:
                return []
            docs = [self._to_document(r) for r in results.docs]
            log_debug(f"Moss async_search returned {len(docs)} results for '{query}'")
            return docs
        except Exception as e:
            log_error(f"Error searching Moss index '{self.index_name}': {e}")
            return []

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete(self) -> bool:
        """Delete the entire index. Returns True on success."""
        try:
            self._run(self._client.delete_index(self.index_name))
            self._index_loaded = False
            return True
        except Exception as e:
            log_error(f"Error deleting Moss index: {e}")
            return False

    def delete_by_id(self, id: str) -> bool:
        """Delete a single document by ID."""
        try:
            self._run(self._client.delete_docs(self.index_name, [id]))
            return True
        except Exception as e:
            log_error(f"Error deleting document '{id}' from Moss: {e}")
            return False

    def delete_by_name(self, name: str) -> bool:
        """Not supported — Moss does not index by document name."""
        log_warning("delete_by_name is not supported by MossVectorDb.")
        return False

    def delete_by_metadata(self, metadata: dict[str, Any]) -> bool:
        """Not supported — use delete_by_id() for targeted removal."""
        log_warning("delete_by_metadata is not supported by MossVectorDb.")
        return False

    def delete_by_content_id(self, content_id: str) -> bool:
        """Not supported — use delete_by_id() for targeted removal."""
        log_warning("delete_by_content_id is not supported by MossVectorDb.")
        return False

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def optimize(self) -> None:
        """No-op: Moss manages its own index optimization."""

    def get_supported_search_types(self) -> list[str]:
        """Return the search types supported by Moss."""
        return ["vector", "keyword", "hybrid"]
