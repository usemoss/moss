"""Runnable webhook server: AgentPhone phone number, Moss-grounded answers.

Follows the AgentPhone voice-webhook tool-calling pattern from
https://docs.agentphone.ai/documentation/guides/calls - immediate interim
NDJSON, then a Claude tool-calling loop with Moss as the only tool, then
the final answer line.

Flow:

1. AgentPhone delivers an ``agent.message`` webhook for every caller turn.
2. We verify the HMAC signature.
3. For voice, we stream NDJSON: an interim filler line, then the Claude +
   Moss tool-call result.
4. For SMS/iMessage, we run the same tool loop and return a single JSON
   ``{"text": "..."}`` body.
5. For ``agent.call_ended`` we just log and ack.

Run::

    uv sync
    cp .env.example .env  # fill in keys
    uv run python server.py

Expose this to AgentPhone with ngrok (or any tunnel) and register the
public URL via ``POST https://api.agentphone.ai/v1/webhooks``.
"""

from __future__ import annotations

import logging
import os

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from moss import DocumentInfo, MossClient

from moss_agentphone import MossAgentPhoneBridge, verify_webhook_signature

logger = logging.getLogger("moss_agentphone.server")
logging.basicConfig(level=logging.INFO)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


load_dotenv()

WEBHOOK_SECRET = _require_env("AGENTPHONE_WEBHOOK_SECRET")
INDEX_NAME = _require_env("MOSS_INDEX_NAME")

moss_client = MossClient(
    _require_env("MOSS_PROJECT_ID"),
    _require_env("MOSS_PROJECT_KEY"),
)
bridge = MossAgentPhoneBridge(
    moss_client=moss_client,
    index_name=INDEX_NAME,
    anthropic_client=AsyncAnthropic(api_key=_require_env("ANTHROPIC_API_KEY")),
    model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
)

DEMO_DOCS = [
    DocumentInfo(
        id="refunds",
        text="Refunds are processed within 3-5 business days after approval.",
    ),
    DocumentInfo(
        id="support-hours",
        text="Customer support is available Monday to Friday, 9am to 6pm IST.",
    ),
    DocumentInfo(
        id="reset-password",
        text=(
            "To reset your password, go to Settings, then Security, choose "
            "Reset Password, and follow the email verification link."
        ),
    ),
    DocumentInfo(
        id="shipping",
        text="Free shipping on orders over $50 in the contiguous US.",
    ),
    DocumentInfo(
        id="returns",
        text="Returns are accepted within 30 days of purchase with original packaging.",
    ),
]


async def _ensure_demo_index(client: MossClient, index_name: str) -> None:
    existing = await client.list_indexes()
    if any(index.name == index_name for index in existing):
        return
    logger.info("Seeding demo index '%s' with %d docs", index_name, len(DEMO_DOCS))
    await client.create_index(index_name, DEMO_DOCS)


app = FastAPI(title="Moss + AgentPhone webhook")


@app.on_event("startup")
async def _startup() -> None:
    await _ensure_demo_index(moss_client, INDEX_NAME)
    await bridge.load_index()
    logger.info("Bridge ready, listening for AgentPhone webhooks")


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
    event_type = event.get("event")
    channel = event.get("channel")
    logger.info(
        "delivery=%s event=%s channel=%s", x_webhook_id, event_type, channel
    )

    if event_type == "agent.message" and channel == "voice":
        transcript = (event.get("data") or {}).get("transcript", "")
        return StreamingResponse(
            bridge.voice_response_stream(transcript),
            media_type="application/x-ndjson",
        )

    if event_type == "agent.message" and channel in {"sms", "mms", "imessage"}:
        message = (event.get("data") or {}).get("message", "")
        return {"text": await bridge.run_tool_call(message)}

    # agent.call_ended, agent.reaction, etc.: ack and move on.
    return {"ok": True}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
