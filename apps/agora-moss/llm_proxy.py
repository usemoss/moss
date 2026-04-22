"""Local dev proxy: logs Agora's LLM requests, cleans payload, forwards upstream.

Mounted at ``/llm/chat/completions`` by ``server.py`` when ``LLM_PROXY_UPSTREAM``
is set. Useful when the chosen LLM provider is strict about OpenAI schema
(e.g. Gemini's OpenAI-compat endpoint rejects the extra ``turn_id`` /
``timestamp`` / ``interruptable`` fields Agora's ConvoAI adds to each request).
"""
from __future__ import annotations

import gzip
import json
import os
import zlib
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

ALLOWED_MSG_KEYS = {"role", "content", "name", "tool_calls", "tool_call_id", "function_call"}
ALLOWED_TOP_KEYS = {
    "model", "messages", "tools", "tool_choice", "temperature", "top_p", "top_k",
    "n", "stream", "stop", "max_tokens", "presence_penalty", "frequency_penalty",
    "logit_bias", "user", "response_format", "seed",
}
ALLOWED_TOOL_KEYS = {"type", "function"}
ALLOWED_TOOL_FN_KEYS = {"name", "description", "parameters"}


def _decode(body: bytes, encoding: str) -> str:
    try:
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)
    except Exception:
        pass
    return body.decode("utf-8", errors="replace")


def _clean_payload(parsed: dict, model: str | None) -> dict:
    """Drop non-OpenAI-spec fields Agora adds; inject model if provided."""
    out = {k: v for k, v in parsed.items() if k in ALLOWED_TOP_KEYS}
    if model and "model" not in out:
        out["model"] = model
    msgs: list = []
    for m in out.get("messages", []):
        if not isinstance(m, dict):
            msgs.append(m)
            continue
        msgs.append({k: v for k, v in m.items() if k in ALLOWED_MSG_KEYS})
    out["messages"] = msgs
    if "tools" in out:
        cleaned_tools: list = []
        for t in out["tools"]:
            if not isinstance(t, dict):
                cleaned_tools.append(t)
                continue
            tt = {k: v for k, v in t.items() if k in ALLOWED_TOOL_KEYS}
            if isinstance(tt.get("function"), dict):
                tt["function"] = {
                    k: v for k, v in tt["function"].items() if k in ALLOWED_TOOL_FN_KEYS
                }
            cleaned_tools.append(tt)
        out["tools"] = cleaned_tools
    return out


# Module-level client reused across requests so a per-request transport isn't
# spun up each time, and so no client is leaked if a streaming response is
# abandoned mid-flight. A mounted sub-app's lifespan is not executed by the
# parent Starlette app, which is why this lives here rather than in lifespan.
_client = httpx.AsyncClient(timeout=60)

app = FastAPI()


@app.post("/chat/completions")
async def chat_completions(request: Request) -> Response:
    upstream = os.environ.get("LLM_PROXY_UPSTREAM")
    if not upstream:
        return JSONResponse(
            {"error": "LLM_PROXY_UPSTREAM is not set; proxy is disabled"},
            status_code=503,
        )
    upstream_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL")

    body = await request.body()
    parsed: dict | None = None
    try:
        parsed = json.loads(body)
        print(f"===== AGORA -> LLM PROXY =====\n{json.dumps(parsed, indent=2)[:2000]}", flush=True)
    except Exception:
        print(f"===== AGORA -> LLM PROXY (non-json) =====\n{body[:500]!r}", flush=True)

    forward_headers = {
        "Authorization": f"Bearer {upstream_key}",
        "Content-Type": "application/json",
    }
    if isinstance(parsed, dict):
        cleaned = _clean_payload(parsed, model)
        forward_body = json.dumps(cleaned).encode()
        stream = bool(cleaned.get("stream"))
    else:
        forward_body = body
        stream = False

    if stream:
        # Peek at the upstream status before committing to a streaming response:
        # if upstream errored, return a non-streaming JSON error with the real
        # status code so callers don't see a 200 text/event-stream wrapping a 4xx.
        req = _client.build_request("POST", upstream, headers=forward_headers, content=forward_body)
        r = await _client.send(req, stream=True)
        if r.status_code >= 400:
            err = await r.aread()
            await r.aclose()
            encoding = r.headers.get("content-encoding", "")
            decoded = _decode(err, encoding)
            print(f"UPSTREAM status: {r.status_code}\n{decoded[:2000]}", flush=True)
            return Response(
                content=decoded,
                status_code=r.status_code,
                media_type=r.headers.get("content-type", "application/json"),
            )

        async def gen() -> AsyncIterator[bytes]:
            try:
                async for chunk in r.aiter_bytes():
                    yield chunk
            finally:
                await r.aclose()

        return StreamingResponse(gen(), status_code=r.status_code, media_type="text/event-stream")

    r = await _client.post(upstream, headers=forward_headers, content=forward_body)
    print(f"UPSTREAM status: {r.status_code}\n{r.text[:500]}", flush=True)
    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=r.headers.get("content-type", "application/json"),
    )
