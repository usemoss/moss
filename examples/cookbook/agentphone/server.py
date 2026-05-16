"""AgentPhone voice webhook, backed by Moss + Claude tool calling.

Single-file cookbook. Module-level ``TOOLS``, ``TOOL_HANDLERS``, and
``run_tool_call`` mirror the structure of AgentPhone's reference:
https://docs.agentphone.ai/documentation/guides/calls

Voice only. Caller speaks, AgentPhone transcribes and POSTs the turn to
``/webhook``. We stream an interim NDJSON line so the caller hears
something while Claude runs a tool-call loop with ``moss_search``, then
stream the grounded answer.

Run::

    uv run python create_index.py    # one-time
    uv run python server.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from moss import MossClient, QueryOptions

logger = logging.getLogger("moss_agentphone")
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")


# --- env + clients ---------------------------------------------------------

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


load_dotenv()

WEBHOOK_SECRET = _require_env("AGENTPHONE_WEBHOOK_SECRET")
INDEX_NAME = _require_env("MOSS_INDEX_NAME")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

moss_client = MossClient(
    _require_env("MOSS_PROJECT_ID"),
    _require_env("MOSS_PROJECT_KEY"),
)
anthropic_client = AsyncAnthropic(api_key=_require_env("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "You are a friendly customer-support agent on a phone call. "
    "When the caller asks about company policies, orders, refunds, "
    "shipping, returns, account help, or product facts, call the "
    "moss_search tool first and answer using ONLY what it returns. "
    "If the search returns nothing relevant, say so honestly. Keep "
    "replies short and conversational, two to three sentences."
)


# --- tools (AgentPhone reference shape) ------------------------------------

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


# ANSI color codes used to make the Moss block easy to spot at a glance.
_M = "\033[1;95m"   # bold bright magenta
_C = "\033[96m"     # bright cyan
_D = "\033[2m"      # dim
_R = "\033[0m"      # reset


def _preview(text: str, words: int = 12) -> str:
    tokens = (text or "").split()
    head = " ".join(tokens[:words])
    return head + ("..." if len(tokens) > words else "")


async def _moss_search(args: dict[str, Any]) -> str:
    query = (args or {}).get("query", "").strip()
    if not query:
        return "moss_search requires a non-empty query string."

    result = await moss_client.query(
        INDEX_NAME, query, QueryOptions(top_k=5, alpha=0.8)
    )
    docs = result.docs
    took = (
        f"{result.time_taken_ms}ms"
        if result.time_taken_ms is not None
        else "n/a"
    )

    logger.info("%s[moss] search%s", _M, _R)
    logger.info("%s[moss]%s   query: %s%r%s", _M, _R, _C, query, _R)
    logger.info("%s[moss]%s   docs:  %s%d%s", _M, _R, _M, len(docs), _R)
    logger.info("%s[moss]%s   time:  %s%s%s", _M, _R, _D, took, _R)
    for i, doc in enumerate(docs, start=1):
        text = (getattr(doc, "text", "") or "").strip()
        logger.info(
            "%s[moss]%s   %s%d.%s %s",
            _M, _R, _D, i, _R, _preview(text),
        )

    if not docs:
        return "No relevant excerpts found."
    return "\n".join(
        f"{i}. {getattr(d, 'text', '')}"
        for i, d in enumerate(docs, start=1)
    )


TOOL_HANDLERS = {"moss_search": _moss_search}


# --- tool-call loop --------------------------------------------------------

async def run_tool_call(
    user_message: str,
    history: list[dict[str, Any]],
) -> str:
    """Run Claude with TOOLS and return the final text response."""
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_message}]

    for _ in range(5):
        response = await anthropic_client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=SYSTEM_PROMPT,
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
            handler = TOOL_HANDLERS.get(block.name)
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


def _to_anthropic_history(
    recent: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Convert AgentPhone's ``recentHistory`` into Anthropic message format."""
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


# --- signature verification ------------------------------------------------

def verify_webhook_signature(
    *, secret: str, timestamp: str, body: bytes, signature: str,
) -> bool:
    signed = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# --- FastAPI app -----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await moss_client.load_index(INDEX_NAME)
    logger.info("Index loaded, listening for AgentPhone webhooks")
    yield


app = FastAPI(title="Moss + AgentPhone webhook", lifespan=lifespan)


@app.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_signature: str = Header(...),
    x_webhook_timestamp: str = Header(...),
    x_webhook_id: str = Header(...),
    x_webhook_event: str = Header(...),
):
    body = await request.body()
    if not verify_webhook_signature(
        secret=WEBHOOK_SECRET,
        timestamp=x_webhook_timestamp,
        body=body,
        signature=x_webhook_signature,
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    event = await request.json()
    logger.info(
        "delivery=%s event=%s channel=%s",
        x_webhook_id,
        event.get("event"),
        event.get("channel"),
    )

    if event.get("event") != "agent.message" or event.get("channel") != "voice":
        # SMS / iMessage / call_ended / etc.: ack and move on.
        return {"ok": True}

    data = event.get("data") or {}
    transcript = data.get("transcript", "")
    history = _to_anthropic_history(event.get("recentHistory"))

    async def generate() -> AsyncIterator[bytes]:
        # Recommended by AgentPhone: stream an interim line immediately so
        # the caller hears something while the tool loop runs.
        yield _ndjson({"text": "Let me check that for you.", "interim": True})
        try:
            answer = await run_tool_call(transcript, history)
        except Exception:
            logger.exception("tool-call loop failed")
            answer = "Sorry, I ran into a problem. Could you try again?"
        yield _ndjson({"text": answer})

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _ndjson(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload) + "\n").encode()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
