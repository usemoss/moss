from __future__ import annotations

import asyncio
from typing import List, Optional, Tuple

from moss_core import (
    AddDocumentsOptions as _RustAddDocumentsOptions,
    DocumentInfo,
    GetDocumentsOptions,
    MutationOptions,
    QueryOptions,
    SearchResult,
    SessionIndex as _RustSessionIndex,
    PushIndexResult,
)


class SessionIndex:
    """
    A local in-session index for real-time indexing and querying.

    All operations (add_docs, delete_docs, query) run entirely in-memory
    with no cloud round trips. Call push_index() at session end to persist
    the index to the cloud for bookkeeping and future retrieval.

    Usage telemetry is tracked and reported automatically in the background.

    Example:
        ```python
        # Auto-loads from cloud if the index exists, starts fresh if not
        session = await client.session(index_name="session-abc")

        await session.add_docs([DocumentInfo(id="1", text="Customer asked about billing")])
        results = await session.query("billing question")

        result = await session.push_index()
        # optionally: await client.get_job_status(result.job_id)
        ```
    """

    def __init__(self, name: str, model_id: str, _inner: "_RustSessionIndex") -> None:
        self._model_id = model_id
        self._inner = _inner

    @classmethod
    def _create(
        cls,
        name: str,
        model_id: str,
        project_id: str,
        project_key: str,
        client_id: Optional[str] = None,
    ) -> "SessionIndex":
        inner = _RustSessionIndex(name, model_id, project_id, project_key, client_id)
        return cls(name, model_id, inner)

    @property
    def name(self) -> str:
        """The index name."""
        return self._inner.name

    @property
    def doc_count(self) -> int:
        """Number of documents in the local session index."""
        return self._inner.doc_count

    async def add_docs(
        self,
        docs: List[DocumentInfo],
        options: Optional[MutationOptions] = None,
    ) -> Tuple[int, int]:
        """
        Add or update documents in the local session index.

        Embeddings are generated locally via Rust core — no cloud round trip.

        Args:
            docs: Documents to add. When using model_id='custom', each doc
                  must have .embedding set.
            options: Mutation options (e.g. upsert behavior).

        Returns:
            Tuple of (added_count, updated_count).
        """
        rust_opts = None
        if options is not None:
            upsert = bool(options.upsert) if options.upsert is not None else True
            rust_opts = _RustAddDocumentsOptions(upsert=upsert)
        if self._model_id == "custom":
            embeddings = self._get_custom_embeddings(docs)
            return await asyncio.to_thread(
                self._inner.add_docs,
                docs,
                embeddings,
                rust_opts,
            )
        return await asyncio.to_thread(self._inner.add_docs_text, docs, rust_opts)

    async def delete_docs(self, doc_ids: List[str]) -> int:
        """
        Delete documents from the local session index by their IDs.

        Returns:
            Number of documents deleted.
        """
        return await asyncio.to_thread(self._inner.delete_docs, doc_ids)

    async def get_docs(
        self,
        options: Optional[GetDocumentsOptions] = None,
    ) -> List[DocumentInfo]:
        """Retrieve documents from the local session index."""
        return await asyncio.to_thread(self._inner.get_docs, options)

    async def query(
        self,
        query: str,
        options: Optional[QueryOptions] = None,
    ) -> SearchResult:
        """
        Perform a semantic search over the local session index.

        Runs entirely in-memory (~1-10ms). No cloud call.

        Args:
            query: The search query text.
            options: Query options (top_k, alpha, embedding, filter). Example filter:
                QueryOptions(filter={"$and": [
                    {"field": "type", "condition": {"$eq": "faq"}},
                    {"field": "priority", "condition": {"$gt": "5"}},
                ]})

        Returns:
            SearchResult with scored documents.
        """
        top_k = getattr(options, "top_k", None)
        top_k = top_k if top_k is not None else 5
        alpha = getattr(options, "alpha", None)
        alpha = alpha if alpha is not None else 0.8
        query_embedding = getattr(options, "embedding", None)
        filter_ = getattr(options, "filter", None)

        if query_embedding is None:
            if self._model_id == "custom":
                raise ValueError(
                    "This session uses custom embeddings. "
                    "Provide a query embedding via QueryOptions.embedding."
                )
            return await asyncio.to_thread(
                self._inner.query_text,
                query,
                top_k,
                alpha,
                filter_,
            )

        return await asyncio.to_thread(
            self._inner.query,
            query,
            top_k,
            list(query_embedding),
            alpha,
            filter_,
        )

    async def push_index(self) -> PushIndexResult:
        """
        Push the local session index to the cloud.

        Sends all documents with their locally-computed embeddings to the
        backend. The cloud index is created or replaced if one already exists
        with the same name. No server-side re-embedding occurs.

        Returns:
            PushIndexResult with job_id, index_name, doc_count, and status.
        """
        return await asyncio.to_thread(self._inner.push_index)

    async def _get_embedding_service(self) -> None:
        if self._model_id != "custom":
            await asyncio.to_thread(self._inner.load_model)

    def _get_custom_embeddings(self, docs: List[DocumentInfo]) -> List[List[float]]:
        missing = [doc.id for doc in docs if not getattr(doc, "embedding", None)]
        if missing:
            raise ValueError(
                f"Documents missing .embedding for custom model: {missing}. "
                "All documents must have .embedding set when using model_id='custom'."
            )
        return [list(doc.embedding) for doc in docs]  # type: ignore[arg-type]
