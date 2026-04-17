# agora-moss

Moss semantic search for [Agora Conversational AI](https://docs.agora.io/en/conversational-ai/overview/product-overview), exposed as a single MCP tool (`search_knowledge_base`) over streamable HTTP.

Drop it behind a public URL, add one `mcp_servers` entry to your ConvoAI `join` body, and your voice agent can search your Moss index. Nothing else changes — the package never owns the LLM hop.

This is the Agora analog of [`vapi-moss`](../vapi-moss) and [`elevenlabs-moss`](../elevenlabs-moss).

## Install

```bash
pip install agora-moss
# or
uv add agora-moss
```

## Quickstart

```python
import uvicorn
from agora_moss import MossAgoraSearch, create_mcp_app

search = MossAgoraSearch(
    project_id="moss-project-id",
    project_key="moss-project-key",
    index_name="my-index",
    top_k=5,
    alpha=0.8,
)

mcp = create_mcp_app(search)
app = mcp.streamable_http_app()

uvicorn.run(app, host="0.0.0.0", port=8080)
```

Expose the server at a public URL, then point Agora ConvoAI at it by adding this to your `join` body:

```json
"llm": {
  "mcp_servers": [{
    "name": "moss",
    "endpoint": "https://<public-host>/mcp",
    "transport": "streamable_http",
    "allowed_tools": ["search_knowledge_base"]
  }]
},
"advanced_features": { "enable_tools": true }
```

Agora constraints (verified April 2026):

- Server entry `name`: ≤48 chars, alphanumeric only (no hyphens / underscores).
- Transport: `streamable_http` only.
- `advanced_features.enable_tools` must be `true`.

## Public API

| Symbol | Kind | Purpose |
|---|---|---|
| `MossAgoraSearch(*, project_id, project_key, index_name, top_k=5, alpha=0.8)` | class | Moss adapter; `async load_index()`, `async search(query) -> AgoraSearchResult`. |
| `create_mcp_app(search) -> FastMCP` | function | Returns a FastMCP server exposing `search_knowledge_base`; runs `search.load_index()` in its lifespan. |
| `AgoraSearchResult` | dataclass | `documents: list[dict]`, `time_taken_ms: int | None`. |

## Demo app

See [`apps/agora-moss`](../../apps/agora-moss) for a runnable end-to-end demo (Docker image + `start_agent.py` that calls ConvoAI's `join` REST).

## Dependencies

- `moss>=1.0.0`
- `mcp>=1.2` (Model Context Protocol Python SDK, FastMCP)
- Python `>=3.10,<3.15`

## License

BSD-2-Clause. See repository root.
