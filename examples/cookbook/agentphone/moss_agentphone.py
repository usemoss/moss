"""Moss-grounded tool-calling bridge for AgentPhone webhooks.

This module implements the pattern AgentPhone recommends for voice webhooks:
stream an interim NDJSON line immediately, then run an LLM tool-calling
loop in the background, then stream the final spoken answer. Moss semantic
search is exposed to the model as a single ``moss_search`` tool, so the LLM
decides when to search and what query to use.

Reference: AgentPhone "Example: tool-calling handler (Python / Flask)" in
https://docs.agentphone.ai/documentation/guides/calls

Names match the AgentPhone reference example: ``TOOLS`` (the schema list),
``TOOL_HANDLERS`` (the name-to-callable mapping), and ``run_tool_call``
(the bounded Claude loop).

What you use from here:

- :func:`verify_webhook_signature` - HMAC-SHA256 check for the
  ``X-Webhook-Signature`` / ``X-Webhook-Timestamp`` headers.
- :class:`MossAgentPhoneBridge` - holds ``TOOL_HANDLERS``, runs
  ``run_tool_call``, and exposes ``voice_response_stream`` for voice
  webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from moss import MossClient, QueryOptions

__all__ = [
    "TOOLS",
    "verify_webhook_signature",
    "MossAgentPhoneBridge",
    "AgentPhoneAPI",
]

logger = logging.getLogger(__name__)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "moss_search",
        "description": (
            "Search the Moss knowledge base for documents that could "
            "answer the caller's question (refunds, shipping, returns, "
            "account help, policies, product facts, etc.). Call this "
            "whenever the caller asks for something that should be looked "
            "up. Pass a focused natural language query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural-language question or lookup text.",
                }
            },
            "required": ["query"],
        },
    }
]


def verify_webhook_signature(
    *,
    secret: str,
    timestamp: str,
    body: bytes,
    signature: str,
) -> bool:
    """Return True if the AgentPhone webhook signature is valid.

    AgentPhone signs ``{timestamp}.{raw_body}`` with HMAC-SHA256 using the
    secret returned at registration. The header value is
    ``sha256=<hex_digest>``.
    """
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


@dataclass
class MossAgentPhoneBridge:
    """Run a Claude tool-calling loop with Moss as the only tool.

    The model decides when to search and writes the query itself. Use
    :meth:`run_tool_call` for SMS-style turns and
    :meth:`voice_response_stream` for voice webhook responses (it yields
    the recommended interim filler line before the final answer).
    """

    moss_client: MossClient
    index_name: str
    anthropic_client: Any  # anthropic.AsyncAnthropic or compatible
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 256
    top_k: int = 5
    alpha: float = 0.8
    max_tool_iterations: int = 5
    system_prompt: str = (
        "You are a friendly customer-support agent on a phone call. "
        "When the caller asks about company policies, orders, refunds, "
        "shipping, returns, account help, or product facts, call the "
        "moss_search tool first and answer using ONLY what it returns. "
        "If the search returns nothing relevant, say so honestly and offer "
        "to transfer them to a human. Keep replies short and conversational, "
        "two to three sentences."
    )
    filler_text: str = "Let me check that for you."
    TOOL_HANDLERS: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        self.TOOL_HANDLERS = {
            "moss_search": self._moss_search,
        }

    async def load_index(self) -> None:
        """Pre-load the Moss index into memory for sub-10ms queries."""
        await self.moss_client.load_index(self.index_name)

    async def run_tool_call(self, user_message: str) -> str:
        """Run Claude with tools and return the final text response.

        Mirrors the ``run_tool_call`` reference in AgentPhone's voice
        webhook guide, with Moss as the only registered tool.
        """
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_message}
        ]

        for _ in range(self.max_tool_iterations):
            response = await self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                return _extract_text(response).strip()

            messages.append({"role": "assistant", "content": response.content})
            tool_results = await self._run_requested_tools(response.content)
            messages.append({"role": "user", "content": tool_results})

        logger.warning(
            "moss_agentphone hit max_tool_iterations=%d",
            self.max_tool_iterations,
        )
        return "Sorry, I am having trouble looking that up. Please try again."

    async def voice_response_stream(
        self, transcript: str
    ) -> AsyncIterator[bytes]:
        """Yield NDJSON lines for an AgentPhone voice webhook response.

        First line is the interim filler AgentPhone recommends so the caller
        hears something while the tool loop runs; second line is the
        grounded answer that ends the turn.
        """
        yield self._ndjson({"text": self.filler_text, "interim": True})
        try:
            answer = await self.run_tool_call(transcript)
        except Exception:
            logger.exception("tool-calling loop failed for transcript")
            answer = "Sorry, I ran into a problem. Could you try again?"
        yield self._ndjson({"text": answer})

    async def _run_requested_tools(
        self, content_blocks: Sequence[Any]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content_blocks:
            if getattr(block, "type", None) != "tool_use":
                continue
            handler = self.TOOL_HANDLERS.get(block.name)
            try:
                output = (
                    await handler(block.input)
                    if handler
                    else f"Unknown tool: {block.name}"
                )
            except Exception as exc:
                logger.exception("tool %s failed", block.name)
                output = f"Tool error: {exc}"
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                }
            )
        return results

    async def _moss_search(self, args: dict[str, Any]) -> str:
        query = (args or {}).get("query", "").strip()
        if not query:
            return "moss_search requires a non-empty query string."
        result = await self.moss_client.query(
            self.index_name,
            query,
            QueryOptions(top_k=self.top_k, alpha=self.alpha),
        )
        return _format_docs(result.docs)

    @staticmethod
    def _ndjson(payload: dict[str, Any]) -> bytes:
        return (json.dumps(payload) + "\n").encode()


class AgentPhoneAPI:
    """Minimal async client for AgentPhone outbound calls.

    SMS, MMS, and iMessage replies are not sent through the webhook
    response body - the handler must call ``POST /v1/messages`` to deliver
    the reply. Voice is the only channel where the webhook response body
    drives the spoken turn.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.agentphone.ai",
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send_message(
        self,
        *,
        agent_id: str,
        to_number: str,
        body: str,
        number_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an SMS / iMessage reply via ``POST /v1/messages``."""
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "to_number": to_number,
            "body": body,
        }
        if number_id:
            payload["number_id"] = number_id
        response = await self._client.post("/v1/messages", json=payload)
        response.raise_for_status()
        return response.json()


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return " ".join(parts)


def _format_docs(documents: Sequence[Any]) -> str:
    if not documents:
        return "No relevant excerpts found."
    lines: list[str] = []
    for idx, doc in enumerate(documents, start=1):
        text = getattr(doc, "text", "") or ""
        score = getattr(doc, "score", None)
        suffix = f" (score={score:.2f})" if score is not None else ""
        lines.append(f"{idx}. {text}{suffix}")
    return "\n".join(lines)
