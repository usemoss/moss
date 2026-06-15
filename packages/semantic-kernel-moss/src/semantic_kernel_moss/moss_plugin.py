#
# Copyright (c) 2025, InferEdge Inc.
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Semantic Kernel plugin for Moss semantic search."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Annotated, Any

from moss import MossClient, QueryOptions
from semantic_kernel.functions import kernel_function

__all__ = ["MossPlugin"]

logger = logging.getLogger("semantic_kernel_moss")


class MossPlugin:
    """Provides Moss semantic search as a Semantic Kernel plugin.

    This class manages the MossClient lifecycle and exposes a
    ``@kernel_function``-decorated ``search`` method that Semantic Kernel
    discovers automatically when the plugin is registered.

    Usage::

        import semantic_kernel as sk
        from semantic_kernel_moss import MossPlugin

        moss = MossPlugin(
            project_id="...",
            project_key="...",
            index_name="my-faq-index",
        )
        await moss.load_index()

        kernel = sk.Kernel()
        kernel.add_plugin(moss, plugin_name="moss")

        result = await kernel.invoke(
            function_name="search", plugin_name="moss", query="What is your refund policy?"
        )
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        result_prefix: str = "Relevant knowledge base results:\n\n",
    ):
        """Initialize with Moss credentials and retrieval settings.

        Args:
            project_id: Moss project ID. Falls back to ``MOSS_PROJECT_ID`` env var.
            project_key: Moss project key. Falls back to ``MOSS_PROJECT_KEY`` env var.
            index_name: Name of the Moss index to query.
            top_k: Number of results to retrieve per query.
            alpha: Blend between semantic (1.0) and keyword (0.0) scoring.
            result_prefix: Prefix prepended to formatted search results.
        """
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._result_prefix = result_prefix
        self._index_loaded = False
        self._load_lock = asyncio.Lock()

    async def load_index(self) -> None:
        """Pre-load the Moss index for fast queries.

        Call this before registering the plugin with a Kernel so that
        the first search invocation does not incur index-loading latency.

        This method is safe to call concurrently; only the first call
        will actually load the index.
        """
        async with self._load_lock:
            if self._index_loaded:
                return
            logger.info("Loading Moss index '%s'", self._index_name)
            await self._client.load_index(self._index_name)
            self._index_loaded = True
            logger.info("Moss index '%s' ready", self._index_name)

    @kernel_function(
        name="search",
        description="Search the knowledge base for documents relevant to a query",
    )
    async def search(
        self,
        query: Annotated[str, "The search query to find relevant documents"],
    ) -> str:
        """Query the Moss index and return formatted results.

        Args:
            query: The search query text.

        Returns:
            Formatted string of search results suitable for LLM context,
            or a short message if no results are found.
        """
        if not self._index_loaded:
            raise RuntimeError(
                f"Index '{self._index_name}' not loaded. Call await load_index() first."
            )

        result = await self._client.query(
            self._index_name,
            query,
            options=QueryOptions(top_k=self._top_k, alpha=self._alpha),
        )
        logger.info(
            "Moss query returned %d docs in %sms",
            len(result.docs),
            result.time_taken_ms,
        )

        return self._format_results(result.docs)

    def _format_results(self, documents: Sequence[Any]) -> str:
        """Format Moss search results into a numbered string."""
        if not documents:
            return "No relevant results found."

        lines = [self._result_prefix.rstrip(), ""]
        for idx, doc in enumerate(documents, start=1):
            meta = doc.metadata or {}
            extras = []
            if source := meta.get("source"):
                extras.append(f"source={source}")
            if (score := getattr(doc, "score", None)) is not None:
                extras.append(f"score={score:.3f}")
            suffix = f" ({', '.join(extras)})" if extras else ""
            text = getattr(doc, "text", "") or ""
            lines.append(f"{idx}. {text}{suffix}")
        return "\n".join(lines).strip()
