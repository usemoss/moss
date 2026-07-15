"""Ambient Moss retrieval store for TEN extensions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from moss import MossClient

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
