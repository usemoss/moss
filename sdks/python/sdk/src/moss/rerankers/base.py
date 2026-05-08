from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable

from moss_core import QueryResultDocumentInfo


@runtime_checkable
class Reranker(Protocol):
    """Protocol for reranking search results using a cross-encoder or API.

    Implement this protocol to create custom rerankers. The SDK ships with
    built-in implementations (e.g., CohereReranker).

    Example:
        class MyReranker:
            async def rerank(self, query, documents, top_k=None):
                # Your reranking logic here
                return sorted(documents, key=lambda d: d.score, reverse=True)
    """

    async def rerank(
        self,
        query: str,
        documents: List[QueryResultDocumentInfo],
        top_k: Optional[int] = None,
        **kwargs: Any,
    ) -> List[QueryResultDocumentInfo]:
        """Rerank documents by relevance to the query.

        Args:
            query: The original search query.
            documents: Retrieved documents with initial scores.
            top_k: If set, return only the top-k reranked results.
            **kwargs: Additional provider-specific options.

        Returns:
            Documents reordered by relevance, with updated scores.
        """
        ...
