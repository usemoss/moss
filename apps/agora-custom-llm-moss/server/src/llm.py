"""
Custom LLM endpoint with Moss grounding.

Forked from Agora's custom-llm recipe (MIT):
https://github.com/AgoraIO-Conversational-AI/recipe-agent-custom-llm/blob/main/server/src/llm.py

Agora cloud POSTs here. This file is the whole Moss story:

  ambient (default)  last user text -> query_context -> prepend -> upstream LLM
  tool               advertise search_knowledge_base to the upstream LLM;
                     run Moss in-process if the model calls it (cap 2);
                     stream only the final spoken answer.

Contract:
- POST /chat/completions
- OpenAI SSE: each line is `data: {json}`, end with `data: [DONE]`
- Non-mock requests must send `Authorization: Bearer ...`
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEARCH_KNOWLEDGE_BASE = "search_knowledge_base"
MAX_MOSS_TOOL_CALLS = 2

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": SEARCH_KNOWLEDGE_BASE,
        "description": (
            "Search the knowledge base for facts that answer the user's question. "
            "Pass a focused natural-language query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's question or a focused search query.",
                }
            },
            "required": ["query"],
        },
    },
}

MOCK_RESPONSES = [
    "I'm a custom LLM with Moss on this server. Ask about refunds, shipping, or passwords.",
    "This is the zero-key mock path. Replace me with UPSTREAM_LLM_* for a real model.",
]


# ---------------------------------------------------------------------------
# Request models (Agora ConvoAI / OpenAI chat completions)
# ---------------------------------------------------------------------------


class TextContent(BaseModel):
    type: str = "text"
    text: str


class SystemMessage(BaseModel):
    role: str = "system"
    content: Union[str, List[str]]


class UserMessage(BaseModel):
    role: str = "user"
    content: Union[str, List[Union[TextContent, Dict]]]


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: Union[str, List[TextContent], None] = None
    tool_calls: Optional[List[Dict]] = None


class ToolMessage(BaseModel):
    role: str = "tool"
    content: Union[str, List[str]]
    tool_call_id: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]]
    stream: bool = True
    stream_options: Optional[Dict] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[Union[str, Dict]] = None
    response_format: Optional[Dict] = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def load_server_env(server_dir: Path | None = None) -> None:
    """Load server/.env then server/.env.local so a filled .env.example is enough."""
    root = server_dir or Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.local", override=True)


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def last_user_text(messages: list) -> str:
    """Extract the latest user utterance. Do not log it (transcripts can be PII)."""
    for msg in reversed(messages):
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "user":
            continue
        content = getattr(msg, "content", None) if not isinstance(msg, dict) else msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                return str(first.get("text") or "")
            return str(getattr(first, "text", "") or "")
    return ""


def message_as_dict(msg: Any) -> dict[str, Any]:
    if isinstance(msg, dict):
        return dict(msg)
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    return {"role": getattr(msg, "role", "user"), "content": getattr(msg, "content", "")}


class MossHandle:
    """Thin wrapper: query_context + last_time_taken_ms. Fail-open."""

    def __init__(self, session: Any | None):
        self.session = session

    async def query_context(self, user_text: str) -> str:
        if self.session is None:
            return ""
        try:
            t0 = time.perf_counter()
            context = await self.session.query_context(user_text)
            wall_ms = (time.perf_counter() - t0) * 1000.0
            sdk_ms = getattr(self.session, "last_time_taken_ms", None)
            logger.info(
                "[retrieval-latency] backend=moss(in-process) "
                "time_taken_ms=%s (wall_clock=%.0fms)",
                sdk_ms,
                wall_ms,
            )
            return context or ""
        except Exception as exc:  # noqa: BLE001 - voice/SSE loop must continue
            logger.error("Moss query failed (%s): %s", type(exc).__name__, exc)
            return ""


async def open_moss() -> MossHandle:
    """Best-effort session. Missing creds / import / open => empty handle."""
    project_id = os.getenv("MOSS_PROJECT_ID", "").strip()
    project_key = os.getenv("MOSS_PROJECT_KEY", "").strip()
    index_name = os.getenv("MOSS_INDEX_NAME", "").strip()
    if not (project_id and project_key and index_name):
        logger.info("Moss disabled (set MOSS_PROJECT_ID / MOSS_PROJECT_KEY / MOSS_INDEX_NAME)")
        return MossHandle(None)
    try:
        from ten_moss import MossSessionManager
    except Exception as exc:  # noqa: BLE001
        logger.error("ten-moss import failed: %s", exc)
        return MossHandle(None)
    session = MossSessionManager(
        project_id=project_id,
        project_key=project_key,
        index_name=index_name,
        model_id=os.getenv("MOSS_MODEL_ID", "moss-minilm"),
        top_k=int(os.getenv("MOSS_TOP_K", "3")),
        alpha=float(os.getenv("MOSS_ALPHA", "0.8")),
    )
    try:
        await session.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("Moss session failed to open: %s", exc)
        return MossHandle(None)
    logger.info("Moss session opened on index %s", index_name)
    return MossHandle(session)


def require_bearer(authorization: Optional[str], mock: bool) -> None:
    if mock:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization: Bearer required")
    token = authorization.split(" ", 1)[1].strip()
    expected = os.getenv("CUSTOM_LLM_API_KEY", "").strip()
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def make_chunk(chunk_id: str, model: str, content: str, finish_reason=None) -> str:
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or "moss-custom-llm",
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def make_role_chunk(chunk_id: str, model: str) -> str:
    chunk = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or "moss-custom-llm",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


async def stream_answer(text: str, model: str):
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    yield make_role_chunk(chunk_id, model)
    words = (text or "").split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else f" {word}"
        if token:
            yield make_chunk(chunk_id, model, token)
    yield make_chunk(chunk_id, model, "", finish_reason="stop")
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Ambient: search, then answer
# ---------------------------------------------------------------------------


async def ambient_answer(messages: list, moss: MossHandle, mock: bool) -> str:
    user_text = last_user_text(messages)
    context = await moss.query_context(user_text)
    if mock:
        return context or MOCK_RESPONSES[0]
    grounded = list(messages)
    if context:
        grounded = [
            SystemMessage(role="system", content=f"Relevant knowledge from Moss:\n{context}"),
            *messages,
        ]
    return await call_upstream(grounded, tools=None)


# ---------------------------------------------------------------------------
# Tool: LLM decides, Agora never sees the tool
# ---------------------------------------------------------------------------


async def tool_answer(messages: list, moss: MossHandle, mock: bool) -> str:
    if mock:
        user_text = last_user_text(messages)
        context = await moss.query_context(user_text)
        logger.info("[retrieval-latency] tool_called=true (echo-grounding stub)")
        return context or MOCK_RESPONSES[0]

    history = [message_as_dict(m) for m in messages]
    moss_calls = 0
    for _ in range(MAX_MOSS_TOOL_CALLS + 1):
        data = await call_upstream_raw(
            history,
            tools=[SEARCH_TOOL],
            tool_choice="auto",
        )
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            if moss_calls == 0:
                logger.info("[retrieval-latency] tool_called=false (LLM declined to search)")
            return (message.get("content") or "").strip() or MOCK_RESPONSES[0]

        history.append(message)
        for call in tool_calls:
            if moss_calls >= MAX_MOSS_TOOL_CALLS:
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "call_cap",
                        "content": "",
                    }
                )
                continue
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {"query": raw_args}
            query = str((args or {}).get("query") or last_user_text(messages))
            context = ""
            if name == SEARCH_KNOWLEDGE_BASE:
                context = await moss.query_context(query)
                moss_calls += 1
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or f"call_{moss_calls}",
                    "content": context,
                }
            )
    return "I looked that up but I am not sure. Please try again."


async def call_upstream(messages: list, tools: list | None) -> str:
    payload_messages = [message_as_dict(m) for m in messages]
    data = await call_upstream_raw(payload_messages, tools=tools, tool_choice=None)
    choice = (data.get("choices") or [{}])[0]
    return ((choice.get("message") or {}).get("content") or "").strip() or MOCK_RESPONSES[0]


async def call_upstream_raw(
    messages: list[dict[str, Any]],
    *,
    tools: list | None,
    tool_choice: str | None,
) -> dict[str, Any]:
    """Non-streaming upstream call. We stream only the final spoken answer."""
    import httpx

    base = os.getenv("UPSTREAM_LLM_URL", "https://api.openai.com/v1").rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    api_key = os.getenv("UPSTREAM_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not api_key:
        raise HTTPException(status_code=503, detail="UPSTREAM_LLM_API_KEY is not set")
    body: dict[str, Any] = {
        "model": os.getenv("UPSTREAM_LLM_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "stream": False,
    }
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# App factory (ambient default; tool is the second entrypoint)
# ---------------------------------------------------------------------------


def create_app(moss_mode: str = "ambient") -> FastAPI:
    load_server_env()
    mode = (moss_mode or "ambient").strip().lower()
    if mode not in {"ambient", "tool"}:
        mode = "ambient"
    mock = env_flag("MOCK")
    state: dict[str, MossHandle | None] = {"moss": None}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        state["moss"] = await open_moss()
        yield

    app = FastAPI(
        title=f"Moss custom-llm ({mode})",
        description="OpenAI-compatible Chat Completions for Agora Conversational AI.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/chat/completions")
    async def chat_completions(
        request: ChatCompletionRequest,
        authorization: Optional[str] = Header(None, alias="Authorization"),
    ):
        require_bearer(authorization, mock=mock)
        if not request.stream:
            raise HTTPException(
                status_code=400,
                detail="Only streaming mode is supported. Set stream=true.",
            )
        moss = state["moss"] or MossHandle(None)
        if mode == "tool":
            text = await tool_answer(request.messages, moss, mock=mock)
        else:
            text = await ambient_answer(request.messages, moss, mock=mock)
        model = request.model or os.getenv("CUSTOM_LLM_MODEL", "moss-custom-llm")
        return StreamingResponse(stream_answer(text, model), media_type="text/event-stream")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "agora-custom-llm-moss", "moss_mode": mode, "mock": mock}

    return app


# Standalone default: MOSS_MODE env (ambient unless set to tool).
app = create_app(os.getenv("MOSS_MODE", "ambient"))


def run_doctor() -> None:
    """Zero-key smoke: mock ambient + tool, no network, no LLM keys."""
    from fastapi.testclient import TestClient

    os.environ["MOCK"] = "1"
    payload = {
        "model": "mock",
        "stream": True,
        "messages": [{"role": "user", "content": "How long do refunds take?"}],
    }
    for mode in ("ambient", "tool"):
        with TestClient(create_app(mode)) as client:
            ok = client.post("/chat/completions", json=payload)
        if ok.status_code != 200:
            raise SystemExit(f"doctor {mode} HTTP {ok.status_code}: {ok.text}")
        if "data: [DONE]" not in ok.text:
            raise SystemExit(f"doctor {mode}: SSE missing data: [DONE]")
        print(f"doctor {mode}: ok")
    os.environ["MOCK"] = "0"
    with TestClient(create_app("ambient")) as client:
        denied = client.post("/chat/completions", json=payload)
    if denied.status_code != 401:
        raise SystemExit(f"doctor bearer: expected 401, got {denied.status_code}")
    print("doctor bearer: rejected missing Authorization")
    print("doctor: ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moss custom-llm server")
    parser.add_argument("--mock", action="store_true", help="Zero-key mock answers (no upstream LLM)")
    parser.add_argument("--doctor", action="store_true", help="In-process smoke, then exit")
    parser.add_argument("--mode", default=os.getenv("MOSS_MODE", "ambient"), choices=["ambient", "tool"])
    args = parser.parse_args()
    if args.mock:
        os.environ["MOCK"] = "1"
    if args.doctor:
        run_doctor()
    else:
        import uvicorn

        port = int(os.getenv("CUSTOM_LLM_PORT", "8001"))
        logger.info("Starting Moss custom-llm mode=%s mock=%s port=%s", args.mode, args.mock, port)
        uvicorn.run(create_app(args.mode), host="0.0.0.0", port=port)
