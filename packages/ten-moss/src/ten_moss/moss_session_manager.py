"""Moss session manager for TEN extensions."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from moss import MossClient, QueryOptions

from .config import MossSessionConfig

__all__ = ["MossSessionManager"]


def _default_logger() -> Any:
    from loguru import logger

    return logger


class MossSessionManager:
    """Manages a conversational session's grounding in Moss.

    Wraps a Moss session (a local, in-process index) and mirrors the Moss
    Sessions SDK — `open`, `add_docs`, `get_docs`, `delete_docs`, `push_index`,
    `doc_count` — plus one convenience, `query_context`, that returns an
    injection-ready grounding block instead of a raw `SearchResult`.
    `query_context` never raises into the caller: on timeout, error, or no hits
    it returns an empty string so the voice loop keeps flowing.

    When built from a config with `enable_moss=False` (or constructed with
    `enabled=False`), no client is created and every method is a safe no-op.
    """

    def __init__(
        self,
        *,
        project_id: str,
        project_key: str,
        index_name: str,
        model_id: str = "moss-minilm",
        top_k: int = 5,
        alpha: float = 0.8,
        context_header: str = "Relevant knowledge from Moss:",
        timeout_s: float = 2.0,
        enabled: bool = True,
        logger: Any = None,
    ) -> None:
        """Store per-session settings (call `open` to open the session)."""
        self._enabled = enabled
        self._client = MossClient(project_id, project_key) if enabled else None
        self._index_name = index_name
        self._model_id = model_id
        self._top_k = top_k
        self._alpha = alpha
        self._context_header = context_header
        self._timeout_s = timeout_s
        self._log = logger or _default_logger()
        self._session: Any = None

    @property
    def doc_count(self) -> int:
        """Number of documents in the open session (0 before `open`)."""
        return getattr(self._session, "doc_count", 0) if self._session else 0

    async def open(self) -> None:
        """Open the Moss session (create-or-resume the index). No-op if disabled."""
        if not self._enabled or self._client is None:
            return
        self._session = await self._client.session(
            index_name=self._index_name, model_id=self._model_id
        )

    async def query_context(self, user_text: str) -> str:
        """Return grounding for this turn, or '' on blank input / no hits / error."""
        text = (user_text or "").strip()
        if not text or self._session is None:
            return ""
        try:
            result = await asyncio.wait_for(
                self._session.query(text, QueryOptions(top_k=self._top_k, alpha=self._alpha)),
                timeout=self._timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - never break the voice loop
            # Do not log the raw utterance: transcripts can contain PII.
            self._log.error(
                f"[ten-moss] context lookup failed (query_len={len(text)}): "
                f"{type(exc).__name__}: {exc}"
            )
            return ""
        docs = getattr(result, "docs", None) or []
        if not docs:
            return ""
        return self._format_context(docs)

    async def add_docs(self, docs: Sequence[Any]) -> Any:
        """Add or update documents in the session (mirrors `SessionIndex.add_docs`)."""
        if self._session is None:
            return None
        return await self._session.add_docs(list(docs))

    async def get_docs(self) -> Any:
        """Return the documents currently in the session."""
        if self._session is None:
            return []
        return await self._session.get_docs()

    async def delete_docs(self, ids: Sequence[str]) -> Any:
        """Delete documents from the session by id."""
        if self._session is None:
            return None
        return await self._session.delete_docs(list(ids))

    async def push_index(self) -> None:
        """Persist the session to the cloud (durability / cross-agent handoff)."""
        if self._session is None:
            return
        await self._session.push_index()

    @classmethod
    def from_config(cls, config: MossSessionConfig, *, logger: Any = None) -> MossSessionManager:
        """Build a session manager from a MossSessionConfig (respects `enable_moss`)."""
        return cls(
            project_id=config.moss_project_id,
            project_key=config.moss_project_key,
            index_name=config.moss_index_name,
            model_id=config.moss_model_id,
            top_k=config.moss_top_k,
            alpha=config.moss_alpha,
            context_header=config.moss_context_header,
            enabled=config.enable_moss,
            logger=logger,
        )

    def _format_context(self, docs: Sequence[Any]) -> str:
        """Format retrieved passages into a single context block."""
        lines = [self._context_header.rstrip(), ""]
        for idx, doc in enumerate(docs, start=1):
            text = (getattr(doc, "text", "") or "").strip()
            lines.append(f"[{idx}] {text}")
        return "\n".join(lines).strip()
