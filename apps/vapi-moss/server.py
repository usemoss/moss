"""VAPI Custom Tool webhook server powered by Moss semantic search.

Preloads a Moss index at startup for sub-10ms retrieval. When the LLM
decides to search, VAPI sends a tool-calls request with the LLM-refined
query; this server queries Moss and returns results.

Run::

    uv run uvicorn server:app --port 3001
"""

import json
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vapi_moss import MossVapiSearch, verify_vapi_signature

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("vapi_moss_server")

# --- Configuration ---

MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
INDEX_NAME = os.getenv("MOSS_INDEX_NAME")
WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()

moss_search = MossVapiSearch(
    project_id=MOSS_PROJECT_ID,
    project_key=MOSS_PROJECT_KEY,
    index_name=INDEX_NAME,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload Moss index at startup. Fail closed if it can't load."""
    await moss_search.load_index()
    logger.info("Moss index '%s' loaded — server ready", INDEX_NAME)
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/tool/search")
async def tool_search(request: Request):
    """Handle VAPI Custom Tool requests.

    VAPI sends:
        {"message": {"type": "tool-calls", "toolCallList": [
            {"id": "...", "name": "search_knowledge", "parameters": {"query": "..."}}
        ]}}

    We return:
        {"results": [{"toolCallId": "...", "result": "..."}]}
    """
    raw_body = await request.body()

    # Verify signature if secret is configured
    if WEBHOOK_SECRET:
        signature = request.headers.get("x-vapi-signature")
        if not signature:
            return JSONResponse({"results": []}, status_code=401)
        if not verify_vapi_signature(raw_body, signature, WEBHOOK_SECRET):
            return JSONResponse({"results": []}, status_code=401)

    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return JSONResponse({"results": []}, status_code=400)

    message = body.get("message", {})

    if message.get("type") != "tool-calls":
        return JSONResponse({"results": []}, status_code=400)

    # Process each tool call
    results = []
    for tool_call in message.get("toolCallList", []):
        call_id = tool_call.get("id", "")
        function = tool_call.get("function", {})
        params = function.get("arguments", {}) or tool_call.get("parameters", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, ValueError):
                params = {}
        if not isinstance(params, dict):
            params = {}
        query = (params.get("query") or "").strip()

        if not query:
            results.append({"toolCallId": call_id, "result": "No query provided."})
            continue

        try:
            search_result = await moss_search.search(query)
            logger.info(
                "Query: %r — %d docs in %sms",
                query,
                len(search_result.documents),
                search_result.time_taken_ms,
            )

            # Format results as text for the LLM
            lines = []
            for i, doc in enumerate(search_result.documents, 1):
                lines.append(f"{i}. {doc['content']}")
            result_text = "\n".join(lines) if lines else "No results found."

            results.append({"toolCallId": call_id, "result": result_text})
        except Exception:
            logger.exception("Moss search failed for query: %r", query)
            results.append({"toolCallId": call_id, "result": "Search unavailable."})

    return {"results": results}
