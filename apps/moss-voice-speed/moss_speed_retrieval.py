"""Moss retrieval processor for the speed showcase.

Adapted from `pipecat_moss.MossIndexProcessor` (BSD-2-Clause, in this repo) with
three additions for the demo:

1. It **times every lookup** and prints a loud one-line banner so the per-turn
   retrieval latency is visible while you talk to the agent.
2. A `simulate_remote_ms` knob adds an artificial delay *before* the lookup to
   imitate a remote vector-DB round trip — so the same agent audibly lags when
   Moss's in-process speed is taken away.
3. It skips duplicate retrievals for the same user turn.

The actual retrieval is the normal fast Moss path: `client.query(...)` over an
index already loaded locally, which returns a `SearchResult` with `time_taken_ms`.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from typing import Any

from loguru import logger
from moss import MossClient, QueryOptions
from pipecat.frames.frames import Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Context frame types vary across Pipecat versions — accept whichever exists.
_CONTEXT_FRAMES: tuple[type, ...] = ()
try:
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame

    _CONTEXT_FRAMES += (OpenAILLMContextFrame,)
except Exception:  # pragma: no cover
    pass
try:
    from pipecat.frames.frames import LLMContextFrame

    _CONTEXT_FRAMES += (LLMContextFrame,)
except Exception:  # pragma: no cover
    pass

__all__ = ["MossSpeedRetrieval"]


class MossSpeedRetrieval(FrameProcessor):
    """Injects Moss knowledge into the LLM context and reports retrieval latency."""

    def __init__(
        self,
        client: MossClient,
        index_name: str,
        *,
        top_k: int = 5,
        alpha: float = 0.8,
        system_prompt: str = "Relevant knowledge from Moss:\n\n",
        simulate_remote_ms: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._client = client
        self._index_name = index_name
        self._top_k = top_k
        self._alpha = alpha
        self._system_prompt = system_prompt
        self._simulate_remote_ms = max(0, simulate_remote_ms)
        self._last_query: str | None = None
        self._mode = f"remote-sim +{self._simulate_remote_ms} ms" if self._simulate_remote_ms else "Moss (in-process)"

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if not _CONTEXT_FRAMES or not isinstance(frame, _CONTEXT_FRAMES):
            await self.push_frame(frame, direction)
            return

        context = getattr(frame, "context", None)
        if context is None:
            await self.push_frame(frame, direction)
            return

        try:
            query = self._latest_user_text(context.get_messages())
            if query and query != self._last_query:
                self._last_query = query
                await self._ground(context, query)
        except Exception as exc:  # never break the voice loop
            logger.error(f"[moss-speed] retrieval error: {exc}")

        await self.push_frame(frame, direction)

    async def _ground(self, context: Any, query: str) -> None:
        # Simulate the network round trip of a remote vector DB, if enabled.
        if self._simulate_remote_ms:
            await asyncio.sleep(self._simulate_remote_ms / 1000.0)

        t0 = time.perf_counter()
        result = await self._client.query(
            self._index_name, query, options=QueryOptions(top_k=self._top_k, alpha=self._alpha)
        )
        wall_ms = (time.perf_counter() - t0) * 1000.0
        docs = getattr(result, "docs", None) or []
        moss_ms = getattr(result, "time_taken_ms", None)

        added = self._simulate_remote_ms + wall_ms
        moss_str = f"{moss_ms} ms" if moss_ms is not None else f"{wall_ms:.1f} ms"
        logger.info(
            f"⚡ retrieval [{self._mode}] · Moss lookup {moss_str} · "
            f"added to this turn ≈ {added:.0f} ms · {len(docs)} passages"
        )

        if docs:
            context.add_message({"role": "system", "content": self._format_documents(docs)})

    @staticmethod
    def _latest_user_text(messages: Sequence[dict[str, Any]]) -> str | None:
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    return "\n".join(
                        c["text"] for c in content if isinstance(c, dict) and c.get("type") == "text"
                    ).strip()
        return None

    def _format_documents(self, documents: Sequence[Any]) -> str:
        lines = [self._system_prompt.rstrip(), ""]
        for idx, doc in enumerate(documents, start=1):
            text = (getattr(doc, "text", "") or "").strip()
            lines.append(f"[{idx}] {text}")
        return "\n".join(lines).strip()
