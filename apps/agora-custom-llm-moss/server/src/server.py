"""One process, two mounts.

  /llm/chat/completions        ambient
  /llm-tools/chat/completions  tool (Agora never sees the tool)
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from llm import create_app, load_server_env

load_server_env()

app = FastAPI(title="Moss custom-llm", version="1.0.0")
app.mount("/llm", create_app("ambient"))
app.mount("/llm-tools", create_app("tool"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agora-custom-llm-moss"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
