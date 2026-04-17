"""ASGI entrypoint for the agora-moss MCP server.

Runs a single-tool FastMCP streamable-HTTP server. Point your Agora ConvoAI
``join`` body at this server's ``/mcp`` endpoint.

Usage (local dev):

    uv run uvicorn server:app --host 0.0.0.0 --port $PORT

The Moss index is preloaded during FastMCP's lifespan — the server will not
accept tool calls until the preload completes.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from loguru import logger

from agora_moss import MossAgoraSearch, create_mcp_app

REQUIRED_ENV = ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME")


def _require_env() -> dict[str, str]:
    load_dotenv()
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        logger.error("Missing required env vars: {}", ", ".join(missing))
        sys.exit(1)
    return {name: os.environ[name] for name in REQUIRED_ENV}


env = _require_env()
search = MossAgoraSearch(
    project_id=env["MOSS_PROJECT_ID"],
    project_key=env["MOSS_PROJECT_KEY"],
    index_name=env["MOSS_INDEX_NAME"],
)
mcp = create_mcp_app(search)
app = mcp.streamable_http_app()  # ASGI application for uvicorn
