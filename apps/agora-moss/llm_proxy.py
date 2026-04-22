"""Local dev proxy: logs Agora's LLM requests, cleans payload, forwards upstream."""
from __future__ import annotations

import gzip
import json
import os
import zlib

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


def _decode(body: bytes, encoding: str) -> str:
    try:
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)
    except Exception:
        pass
    try:
        return body.decode("utf-8", errors="replace")
    except Exception:
        return repr(body[:500])

UPSTREAM = os.environ["LLM_PROXY_UPSTREAM"]
UPSTREAM_KEY = os.environ.get("LLM_API_KEY", "")
MODEL = os.environ.get("LLM_MODEL")

ALLOWED_MSG_KEYS = {"role", "content", "name", "tool_calls", "tool_call_id", "function_call"}
ALLOWED_TOP_KEYS = {
    "model", "messages", "tools", "tool_choice", "temperature", "top_p", "top_k",
    "n", "stream", "stop", "max_tokens", "presence_penalty", "frequency_penalty",
    "logit_bias", "user", "response_format", "seed",
}
ALLOWED_TOOL_KEYS = {"type", "function"}
ALLOWED_TOOL_FN_KEYS = {"name", "description", "parameters"}


def _clean_payload(parsed: dict) -> dict:
    """Drop non-OpenAI-spec fields Agora adds; inject model if LLM_MODEL is set."""
    out = {k: v for k, v in parsed.items() if k in ALLOWED_TOP_KEYS}
    if MODEL and "model" not in out:
        out["model"] = MODEL
    msgs = []
    for m in out.get("messages", []):
        if not isinstance(m, dict):
            msgs.append(m)
            continue
        msgs.append({k: v for k, v in m.items() if k in ALLOWED_MSG_KEYS})
    out["messages"] = msgs
    if "tools" in out:
        cleaned_tools = []
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

app = FastAPI()


@app.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.body()
    headers = dict(request.headers)
    print("===== AGORA -> LLM PROXY =====")
    print("Headers:", json.dumps({k: v for k, v in headers.items() if k.lower() not in ("authorization",)}, indent=2))
    parsed: dict | None = None
    try:
        parsed = json.loads(body)
        print("Body:", json.dumps(parsed, indent=2)[:2000])
    except Exception:
        print("Body (raw):", body[:500])
    print("================================", flush=True)

    # Forward to Gemini with cleaned payload
    forward_headers = {
        "Authorization": f"Bearer {UPSTREAM_KEY}",
        "Content-Type": "application/json",
    }
    if isinstance(parsed, dict):
        cleaned = _clean_payload(parsed)
        forward_body = json.dumps(cleaned).encode()
        stream = bool(cleaned.get("stream"))
    else:
        forward_body = body
        stream = False

    if stream:
        async def gen():
            client = httpx.AsyncClient(timeout=60)
            try:
                async with client.stream("POST", UPSTREAM, headers=forward_headers, content=forward_body) as r:
                    print(f"UPSTREAM status: {r.status_code}", flush=True)
                    if r.status_code >= 400:
                        err = b"".join([chunk async for chunk in r.aiter_bytes()])
                        print(f"UPSTREAM err body: {err.decode('utf-8', 'replace')[:2000]}", flush=True)
                        yield err
                        return
                    buf = b""
                    async for chunk in r.aiter_bytes():
                        buf += chunk
                        yield chunk
                    print(f"UPSTREAM stream preview: {buf.decode('utf-8', 'replace')[:800]}", flush=True)
            finally:
                await client.aclose()
        return StreamingResponse(gen(), media_type="text/event-stream")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(UPSTREAM, headers=forward_headers, content=forward_body)
        print(f"UPSTREAM status: {r.status_code}", flush=True)
        print(f"UPSTREAM body (first 500): {r.text[:500]}", flush=True)
        try:
            return JSONResponse(r.json(), status_code=r.status_code)
        except Exception:
            return JSONResponse({"error": "non-json upstream"}, status_code=500)
