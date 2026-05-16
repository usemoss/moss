"""Reusable pieces of the Moss + AgentPhone cookbook.

Mirrors AgentPhone's "Example: tool-calling handler" reference shape
(module-level ``TOOLS``, a ``run_tool_call`` loop bounded at five
iterations, ``stop_reason != "tool_use"`` as the exit) but with the
Anthropic client and the per-call ``tool_handlers`` dict passed in as
parameters, so this module stays free of side-effecting env-var reads.

https://docs.agentphone.ai/documentation/guides/calls
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

__all__ = [
    "TOOLS",
    "log_moss_search",
    "ndjson",
    "preview",
    "run_tool_call",
    "to_anthropic_history",
    "verify_webhook_signature",
]

logger = logging.getLogger("moss_agentphone")

# ANSI color codes used to make the Moss block easy to spot at a glance.
_M = "\033[1;95m"   # bold bright magenta
_C = "\033[96m"     # bright cyan
_D = "\033[2m"      # dim
_R = "\033[0m"      # reset


TOOLS: list[dict[str, Any]] = [
    {
        "name": "moss_search",
        "description": (
            "Search the Moss knowledge base for documents that could "
            "answer the caller's question. Pass a focused natural "
            "language query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]


ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


def verify_webhook_signature(
    *, secret: str, timestamp: str, body: bytes, signature: str,
) -> bool:
    """HMAC-SHA256 check for AgentPhone's signed webhook headers."""
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def to_anthropic_history(
    recent: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Map AgentPhone's ``recentHistory`` into Anthropic message format."""
    if not recent:
        return []
    out: list[dict[str, Any]] = []
    for entry in recent:
        text = (entry.get("content") or "").strip()
        if not text:
            continue
        role = "assistant" if entry.get("direction") == "outbound" else "user"
        out.append({"role": role, "content": text})
    return out


def ndjson(payload: dict[str, Any]) -> bytes:
    """Serialize a dict to a single NDJSON line of bytes."""
    return (json.dumps(payload) + "\n").encode()


def preview(text: str, words: int = 12) -> str:
    """Return the first ``words`` words of ``text`` with a trailing ellipsis."""
    tokens = (text or "").split()
    head = " ".join(tokens[:words])
    return head + ("..." if len(tokens) > words else "")


def log_moss_search(
    query: str,
    docs: list[Any],
    time_taken_ms: int | None,
) -> None:
    """Log a colored, multi-line block describing a Moss query result."""
    took = f"{time_taken_ms}ms" if time_taken_ms is not None else "n/a"
    logger.info("%s[moss] search%s", _M, _R)
    logger.info("%s[moss]%s   query: %s%r%s", _M, _R, _C, query, _R)
    logger.info("%s[moss]%s   docs:  %s%d%s", _M, _R, _M, len(docs), _R)
    logger.info("%s[moss]%s   time:  %s%s%s", _M, _R, _D, took, _R)
    for i, doc in enumerate(docs, start=1):
        text = (getattr(doc, "text", "") or "").strip()
        logger.info(
            "%s[moss]%s   %s%d.%s %s",
            _M, _R, _D, i, _R, preview(text),
        )


async def run_tool_call(
    *,
    user_message: str,
    history: list[dict[str, Any]],
    anthropic_client: Any,
    tool_handlers: dict[str, ToolHandler],
    model: str,
    system_prompt: str,
    max_tokens: int = 256,
    max_iterations: int = 5,
) -> str:
    """Run Claude with ``TOOLS`` and return the final text response.

    Mirrors the bounded loop in AgentPhone's reference example, with the
    Anthropic client and the per-call ``tool_handlers`` injected so this
    function stays reusable across deployments.
    """
    messages: list[dict[str, Any]] = [
        *history,
        {"role": "user", "content": user_message},
    ]

    for _ in range(max_iterations):
        response = await anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return _extract_text(response).strip()

        messages.append({"role": "assistant", "content": response.content})

        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            handler = tool_handlers.get(block.name)
            try:
                output = (
                    await handler(block.input)
                    if handler
                    else f"Unknown tool: {block.name}"
                )
            except Exception as exc:
                logger.exception("tool %s failed", block.name)
                output = f"Tool error: {exc}"
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return "Sorry, I am having trouble looking that up. Please try again."


def _extract_text(response: Any) -> str:
    return " ".join(
        block.text
        for block in getattr(response, "content", []) or []
        if getattr(block, "type", None) == "text"
    )
