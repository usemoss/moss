from __future__ import annotations

import os
from typing import Any, List, Optional

import cohere
from moss_core import QueryResultDocumentInfo

from .base import Reranker


class CohereReranker(Reranker):
    """Reranker using the Cohere Python SDK.

    Requires the `cohere` package: pip install cohere

    Example:
        results = await client.query("index", "query",
            rerank=RerankOptions(provider="cohere", api_key="your-cohere-key", top_n=5)
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "rerank-v3.5",
        **kwargs: Any,
    ):
        """Initialize the Cohere reranker.

        Args:
            api_key: Cohere API key. Falls back to COHERE_API_KEY env var.
            model: Cohere rerank model name.
            **kwargs: Reserved for future provider-specific options.
        """
        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cohere API key is required. Pass api_key or set COHERE_API_KEY env var."
            )
        self.model = model
        self.extra_options = kwargs
        self._client = cohere.AsyncClientV2(api_key=self.api_key)

    async def rerank(
        self,
        query: str,
        documents: List[QueryResultDocumentInfo],
        top_k: Optional[int] = None,
        **kwargs: Any,
    ) -> List[QueryResultDocumentInfo]:
        """Rerank documents using the Cohere Rerank API.

        Args:
            query: The search query.
            documents: Documents to rerank.
            top_k: Number of top results to return. Defaults to all documents.

        Returns:
            Documents reordered by Cohere relevance score.
        """
        if not documents:
            return []

        doc_texts = [doc.text for doc in documents]
        resolved_top_k = top_k or len(documents)

        response = await self._client.rerank(
            model=self.model,
            query=query,
            documents=doc_texts,
            top_n=resolved_top_k,
        )

        reranked = []
        for result in response.results:
            original_doc = documents[result.index]
            reranked.append(
                QueryResultDocumentInfo(
                    id=original_doc.id,
                    text=original_doc.text,
                    metadata=original_doc.metadata,
                    score=result.relevance_score,
                )
            )

        return reranked
