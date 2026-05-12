"""Moss semantic search adapter for sim.ai workflow tool calls."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from moss import MossClient, QueryOptions

__all__ = ["MossSimSearch", "SimSearchResult"]

logger = logging.getLogger("sim_moss")


@dataclass
class SimSearchResult:
    """Result from a sim.ai-formatted Moss search.

    Attributes:
        results: List of documents in sim.ai's expected shape.
        time_taken_ms: Moss query latency in milliseconds, if available.
    """

    results: list[dict[str, Any]] = field(default_factory=list)
    time_taken_ms: int | None = None


class MossSimSearch:
    """Moss semantic search formatted for sim.ai workflow tool responses.

    Wraps a Moss index and returns results in the shape expected by sim.ai
    external tool nodes: ``{"content": "...", "score": 0.94, "source": "..."}``.

    Usage::

        from sim_moss import MossSimSearch

        search = MossSimSearch(
            project_id="...",
            project_key="...",
            index_name="my-docs",
        )
        await search.load_index()

        result = await search.search("how do I reset my password?")
        # result.results -> [{"content": "...", "score": 0.94, "source": "faq.md"}, ...]
        # result.time_taken_ms -> 4
    """

    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
    ):
        """Initialize with Moss credentials and retrieval settings.

        Args:
            project_id: Moss project ID. Falls back to ``MOSS_PROJECT_ID`` env var.
            project_key: Moss project key. Falls back to ``MOSS_PROJECT_KEY`` env var.
            index_name: Name of the Moss index to query.
            top_k: Number of results to retrieve per query.
            alpha: Blend between semantic (1.0) and keyword (0.0) scoring.
        """
        self._client = MossClient(project_id=project_id, project_key=project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._index_loaded = False

    async def load_index(self) -> None:
        """Pre-load the Moss index for fast queries.

        Raises on failure so the caller can fail closed at startup.
        """
        logger.info("Loading Moss index '%s'", self._index_name)
        await self._client.load_index(self._index_name)
        self._index_loaded = True
        logger.info("Moss index '%s' ready", self._index_name)

    async def search(self, query: str) -> SimSearchResult:
        """Query the Moss index and return sim.ai-formatted results.

        Args:
            query: The search query text.

        Returns:
            SimSearchResult with documents and timing data.

        Raises:
            RuntimeError: If the index has not been loaded yet.
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

        return SimSearchResult(
            results=self._format_results(result.docs),
            time_taken_ms=result.time_taken_ms,
        )

    @staticmethod
    def _format_results(documents: Sequence[Any]) -> list[dict[str, Any]]:
        """Format Moss search results into sim.ai's document shape."""
        out = []
        for doc in documents:
            entry: dict[str, Any] = {"content": getattr(doc, "text", "") or ""}
            if (score := getattr(doc, "score", None)) is not None:
                entry["score"] = float(score)
            if meta := getattr(doc, "metadata", None):
                if source := meta.get("source"):
                    entry["source"] = source
            out.append(entry)
        return out
