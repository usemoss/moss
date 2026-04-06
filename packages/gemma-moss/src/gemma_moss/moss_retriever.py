#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Moss retrieval adapter for semantic search."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from inferedge_moss import MossClient, QueryOptions, SearchResult

from .formatters import DefaultContextFormatter

__all__ = ["MossRetriever"]

logger = logging.getLogger("gemma_moss")


class MossRetriever:
    """Thin reusable retrieval adapter over the Moss SDK.

    Usage::

        retriever = MossRetriever(index_name="my-index")
        await retriever.load_index()

        # Raw search
        result = await retriever.query("search terms")

        # Formatted for LLM context
        context = await retriever.retrieve("search terms")
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        formatter: Callable[[Sequence[Any]], str | None] | None = None,
    ) -> None:
        """Initialize the retriever.

        Args:
            project_id: Moss project ID. Falls back to ``MOSS_PROJECT_ID`` env var.
            project_key: Moss project key. Falls back to ``MOSS_PROJECT_KEY`` env var.
            index_name: Name of the Moss index to query.
            top_k: Number of results to retrieve per query.
            alpha: Blend between semantic (1.0) and keyword (0.0) scoring.
            formatter: Optional callable to format docs into context. Defaults to
                ``DefaultContextFormatter``.
        """
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._formatter = formatter or DefaultContextFormatter()
        self._index_loaded = False

    async def load_index(self) -> None:
        """Pre-load the Moss index into memory for fast queries."""
        logger.info("Loading Moss index '%s'", self._index_name)
        await self._client.load_index(self._index_name)
        self._index_loaded = True
        logger.info("Moss index '%s' ready", self._index_name)

    async def query(self, query: str) -> SearchResult:
        """Perform a raw semantic search against the Moss index.

        Args:
            query: The search query text.

        Returns:
            Raw ``SearchResult`` from the Moss SDK.

        Raises:
            RuntimeError: If ``load_index()`` has not been called.
        """
        self._ensure_loaded()
        return await self._client.query(
            self._index_name,
            query,
            options=QueryOptions(top_k=self._top_k, alpha=self._alpha),
        )

    async def retrieve(self, query: str) -> str | None:
        """Search and format results into an LLM-ready context string.

        Args:
            query: The search query text.

        Returns:
            Formatted context string, or ``None`` if no documents matched.

        Raises:
            RuntimeError: If ``load_index()`` has not been called.
        """
        result = await self.query(query)
        return self._formatter(result.docs)

    def _ensure_loaded(self) -> None:
        """Raise if the index has not been loaded."""
        if not self._index_loaded:
            raise RuntimeError(
                f"Index '{self._index_name}' not loaded. Call await load_index() first."
            )
