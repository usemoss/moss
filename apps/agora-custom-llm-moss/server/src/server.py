"""Mount ambient (default) and tool custom-llm apps on one process.

Agora cloud calls:
  <public>/llm/chat/completions        ambient (MOSS_MODE default)
  <public>/llm-tools/chat/completions  tool loop (Agora never sees the tool)

Forked layout from the Agora custom-llm recipe (MIT). This file does not
import agora_agent; tokens/startAgent stay in the public recipe if you need them.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from llm import create_app, load_server_env

load_server_env()

app = FastAPI(title="Moss custom-llm (ambient + tool)", version="1.0.0")
app.mount("/llm", create_app("ambient"))
app.mount("/llm-tools", create_app("tool"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agora-custom-llm-moss"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
