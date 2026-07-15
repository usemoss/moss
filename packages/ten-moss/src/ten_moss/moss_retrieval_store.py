"""Ambient Moss retrieval store for TEN extensions."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from moss import MossClient, QueryOptions

from .config import MossRetrievalConfig

__all__ = ["MossRetrievalStore"]


def _default_logger() -> Any:
    from loguru import logger

    return logger


class MossRetrievalStore:
    """Loads a Moss index and returns formatted context for a user query.

    Retrieval never raises into the caller: on timeout, error, or no hits it
    returns an empty string so the voice loop keeps flowing.
    """

    def __init__(
        self,
        *,
        project_id: str,
        project_key: str,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        context_header: str = "Relevant knowledge from Moss:",
        timeout_s: float = 2.0,
        logger: Any = None,
    ) -> None:
        """Store client and per-query retrieval settings."""
        self._client = MossClient(project_id, project_key)
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._context_header = context_header
        self._timeout_s = timeout_s
        self._log = logger or _default_logger()
        self._loaded = False

    def format_context(self, docs: Sequence[Any]) -> str:
        """Format retrieved passages into a single context block."""
        if not docs:
            return self._context_header.rstrip()
        lines = [self._context_header.rstrip(), ""]
        for idx, doc in enumerate(docs, start=1):
            text = (getattr(doc, "text", "") or "").strip()
            lines.append(f"[{idx}] {text}")
        return "\n".join(lines).strip()

    async def load(self) -> None:
        """Load the configured index once at startup. Raises on failure."""
        await self._client.load_index(self._index_name)
        self._loaded = True

    async def retrieve(self, query: str) -> str:
        """Return a context block for `query`, or '' on blank/no-hit/error."""
        text = (query or "").strip()
        if not text:
            return ""
        try:
            result = await asyncio.wait_for(
                self._client.query(
                    self._index_name,
                    text,
                    options=QueryOptions(top_k=self._top_k, alpha=self._alpha),
                ),
                timeout=self._timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - never break the voice loop
            self._log.error(f"[ten-moss] retrieval failed for query={text!r}: {exc}")
            return ""
        docs = getattr(result, "docs", None) or []
        if not docs:
            return ""
        return self.format_context(docs)

    @classmethod
    def from_config(cls, config: MossRetrievalConfig, *, logger: Any = None) -> MossRetrievalStore:
        """Build a store from a MossRetrievalConfig."""
        return cls(
            project_id=config.moss_project_id,
            project_key=config.moss_project_key,
            index_name=config.moss_index_name,
            top_k=config.moss_top_k,
            alpha=config.moss_alpha,
            context_header=config.moss_context_header,
            logger=logger,
        )
