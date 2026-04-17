# agora-moss

Moss semantic search for [Agora Conversational AI](https://docs.agora.io/en/conversational-ai/overview/product-overview), exposed as a single MCP tool over streamable HTTP.

Add one `mcp_servers` entry to your existing ConvoAI `join` body and your voice agent can search your Moss index.

## Install

```bash
pip install agora-moss
```

## Library usage

```python
from agora_moss import MossAgoraSearch, create_mcp_app

search = MossAgoraSearch(
    project_id="...",
    project_key="...",
    index_name="my-index",
)
app = create_mcp_app(search)
# Run `app` under uvicorn; see apps/agora-moss for the full deployment recipe.
```

## Demo app

See `apps/agora-moss/` for a runnable demo (Docker image, `start_agent.py` that wires an Agora ConvoAI `join` call, seed-index script).

## License

BSD-2-Clause. See repository root.
