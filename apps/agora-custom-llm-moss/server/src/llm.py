"""OpenAI-compatible /chat/completions with Moss.

Forked from Agora's custom-llm recipe (MIT):
https://github.com/AgoraIO-Conversational-AI/recipe-agent-custom-llm/blob/main/server/src/llm.py

SSE must end with `data: [DONE]`. Non-mock requests need Authorization: Bearer.
"""

from __future__ import annotations

import argparse
import asyncio
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
MOCK_FALLBACK = (
    "I'm a custom LLM with Moss on this server. Ask about refunds, shipping, or passwords."
)
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": SEARCH_KNOWLEDGE_BASE,
        "description": "Search the knowledge base. Pass a focused natural-language query.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


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


def load_server_env(server_dir: Path | None = None) -> None:
    root = server_dir or Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.local", override=True)


def last_user_text(messages: list) -> str:
    for msg in reversed(messages):
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        if role != "user":
            continue
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                return str(first.get("text") or "")
            return str(getattr(first, "text", "") or "")
    return ""


def as_dict(msg: Any) -> dict[str, Any]:
    if isinstance(msg, dict):
        return dict(msg)
    if hasattr(msg, "model_dump"):
        return msg.model_dump(exclude_none=True)
    return {"role": getattr(msg, "role", "user"), "content": getattr(msg, "content", "")}


async def query_moss(session, user_text: str) -> str:
    if session is None:
        return ""
    try:
        t0 = time.perf_counter()
        context = await session.query_context(user_text)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        sdk_ms = getattr(session, "last_time_taken_ms", None)
        logger.info(
            "[retrieval-latency] backend=moss(in-process) time_taken_ms=%s (wall_clock=%.0fms)",
            sdk_ms,
            wall_ms,
        )
        return context or ""
    except Exception as exc:
        logger.error("Moss query failed (%s): %s", type(exc).__name__, exc)
        return ""


async def open_moss():
    project_id = os.getenv("MOSS_PROJECT_ID", "").strip()
    project_key = os.getenv("MOSS_PROJECT_KEY", "").strip()
    index_name = os.getenv("MOSS_INDEX_NAME", "").strip()
    if not (project_id and project_key and index_name):
        logger.info("Moss disabled (set MOSS_PROJECT_ID / MOSS_PROJECT_KEY / MOSS_INDEX_NAME)")
        return None
    try:
        from ten_moss import MossSessionManager
    except Exception as exc:
        logger.error("ten-moss import failed: %s", exc)
        return None
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
    except Exception as exc:
        logger.error("Moss session failed to open: %s", exc)
        return None
    logger.info("Moss session opened on index %s", index_name)
    return session


def require_bearer(authorization: Optional[str], mock: bool) -> None:
    if mock:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization: Bearer required")
    token = authorization.split(" ", 1)[1].strip()
    expected = os.getenv("CUSTOM_LLM_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=401, detail="CUSTOM_LLM_API_KEY is not set")
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def search_query(raw_args, fallback: str) -> str:
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    return str(args.get("query") or fallback or "")


def sse_chunk(chunk_id: str, model: str, delta: dict, finish_reason=None) -> str:
    body = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or "moss-custom-llm",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(body)}\n\n"


async def stream_answer(text: str, model: str):
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    yield sse_chunk(chunk_id, model, {"role": "assistant", "content": ""})
    words = (text or "").split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else f" {word}"
        if token:
            yield sse_chunk(chunk_id, model, {"content": token})
    yield sse_chunk(chunk_id, model, {}, finish_reason="stop")
    yield "data: [DONE]\n\n"


async def ambient_answer(messages: list, session, mock: bool) -> str:
    context = await query_moss(session, last_user_text(messages))
    if mock:
        return context or MOCK_FALLBACK
    grounded = list(messages)
    if context:
        grounded = [
            SystemMessage(role="system", content=f"Relevant knowledge from Moss:\n{context}"),
            *messages,
        ]
    return await call_upstream(grounded)


async def tool_answer(messages: list, session, mock: bool) -> str:
    if mock:
        context = await query_moss(session, last_user_text(messages))
        logger.info("[retrieval-latency] tool_called=true (mock stub)")
        return context or MOCK_FALLBACK

    history = [as_dict(m) for m in messages]
    moss_calls = 0
    for _ in range(MAX_MOSS_TOOL_CALLS + 1):
        data = await call_upstream(history, tools=[SEARCH_TOOL], raw=True)
        message = ((data.get("choices") or [{}])[0].get("message")) or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            if moss_calls == 0:
                logger.info("[retrieval-latency] tool_called=false (LLM declined to search)")
            return (message.get("content") or "").strip() or MOCK_FALLBACK

        history.append(message)
        for call in tool_calls:
            fn = call.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            query = search_query(raw_args, last_user_text(messages))
            context = ""
            if fn.get("name") == SEARCH_KNOWLEDGE_BASE and moss_calls < MAX_MOSS_TOOL_CALLS:
                context = await query_moss(session, query)
                moss_calls += 1
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id") or f"call_{moss_calls}",
                    "content": context,
                }
            )
    return "I looked that up but I am not sure. Please try again."


async def call_upstream(messages: list, tools: list | None = None, raw: bool = False):
    # Upstream is non-streaming; only the final answer is sent to Agora as SSE.
    import httpx

    payload = [as_dict(m) for m in messages]
    base = os.getenv("UPSTREAM_LLM_URL", "https://api.openai.com/v1").rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    api_key = os.getenv("UPSTREAM_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    if not api_key:
        raise HTTPException(status_code=503, detail="UPSTREAM_LLM_API_KEY is not set")
    body: dict[str, Any] = {
        "model": os.getenv("UPSTREAM_LLM_MODEL", "gpt-4o-mini"),
        "messages": payload,
        "stream": False,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    if raw:
        return data
    return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or MOCK_FALLBACK


def create_app(moss_mode: str = "ambient") -> FastAPI:
    load_server_env()
    mode = moss_mode if moss_mode in {"ambient", "tool"} else "ambient"
    mock = os.getenv("MOCK", "").strip().lower() in {"1", "true", "yes", "on"}
    state: dict[str, Any] = {"session": None, "ready": False}
    init_lock = asyncio.Lock()

    async def get_session():
        # FastAPI does not always run a mounted app's lifespan.
        if not state["ready"]:
            async with init_lock:
                if not state["ready"]:
                    state["session"] = await open_moss()
                    state["ready"] = True
        return state["session"]

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await get_session()
        yield

    app = FastAPI(title=f"Moss custom-llm ({mode})", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
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
            raise HTTPException(status_code=400, detail="Only streaming mode is supported. Set stream=true.")
        session = await get_session()
        if mode == "tool":
            text = await tool_answer(request.messages, session, mock=mock)
        else:
            text = await ambient_answer(request.messages, session, mock=mock)
        model = request.model or os.getenv("CUSTOM_LLM_MODEL", "moss-custom-llm")
        return StreamingResponse(stream_answer(text, model), media_type="text/event-stream")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "agora-custom-llm-moss", "moss_mode": mode, "mock": mock}

    return app


app = create_app(os.getenv("MOSS_MODE", "ambient"))


def run_doctor() -> None:
    from fastapi.testclient import TestClient

    # run_doctor runs in-process from the test suite, so snapshot every env var
    # it flips and restore the originals on the way out (None means "was absent").
    saved_mock = os.environ.get("MOCK")
    saved_key = os.environ.get("CUSTOM_LLM_API_KEY")

    def _restore(name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    try:
        os.environ["MOCK"] = "1"
        payload = {
            "model": "mock",
            "stream": True,
            "messages": [{"role": "user", "content": "How long do refunds take?"}],
        }
        for mode in ("ambient", "tool"):
            with TestClient(create_app(mode)) as client:
                ok = client.post("/chat/completions", json=payload)
            if ok.status_code != 200 or "data: [DONE]" not in ok.text:
                raise SystemExit(f"doctor {mode} failed: {ok.status_code} {ok.text}")
            print(f"doctor {mode}: ok")
        os.environ["MOCK"] = "0"
        with TestClient(create_app("ambient")) as client:
            denied = client.post("/chat/completions", json=payload)
        if denied.status_code != 401:
            raise SystemExit(f"doctor bearer: expected 401, got {denied.status_code}")
        print("doctor bearer: rejected missing Authorization")
        # Temporarily remove the key so the next request runs against an unset
        # key; create_app reloads .env, so pop again after building the app. The
        # outer finally owns the real restore.
        os.environ.pop("CUSTOM_LLM_API_KEY", None)
        test_app = create_app("ambient")
        os.environ.pop("CUSTOM_LLM_API_KEY", None)
        with TestClient(test_app) as client:
            any_token = client.post(
                "/chat/completions",
                json=payload,
                headers={"Authorization": "Bearer anything"},
            )
        if any_token.status_code != 401:
            raise SystemExit(
                f"doctor bearer: unset key should reject any token, got {any_token.status_code}"
            )
        print("doctor bearer: rejected any token while CUSTOM_LLM_API_KEY is unset")
        print("doctor: ok")
    finally:
        _restore("MOCK", saved_mock)
        _restore("CUSTOM_LLM_API_KEY", saved_key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Moss custom-llm server")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--doctor", action="store_true")
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
