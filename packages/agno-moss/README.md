# agno-moss

The Moss in-memory semantic search runtime for [Agno](https://docs.agno.com) agents.

Moss manages embeddings internally and serves queries from an in-memory runtime — sub-10ms lookups, no external embedder, no vector database to run. Point `Knowledge` at `MossRuntime` and Agno agents get instant RAG with zero infrastructure.

## Installation

```bash
pip install agno-moss
# or
uv add agno-moss
```

## Prerequisites

- Moss project ID and project key — get them from the [Moss Portal](https://portal.usemoss.dev)
- Python 3.10+
- An Agno-compatible model provider (OpenAI, Anthropic, etc.)

## Quickstart

```python
import os
from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.models.anthropic import Claude
from agno_moss import MossRuntime

knowledge = Knowledge(
    vector_db=MossRuntime(
        index_name="my-index",
        # Falls back to MOSS_PROJECT_ID / MOSS_PROJECT_KEY env vars
    ),
)

agent = Agent(
    model=Claude(id="claude-sonnet-4-20250514"),
    knowledge=knowledge,
    search_knowledge=True,
    markdown=True,
)

knowledge.load(recreate=False)
agent.print_response("What do you know about our return policy?", stream=True)
```

## Configuration

### MossRuntime

| Parameter | Default | Description |
|---|---|---|
| `index_name` | (required) | Name of the Moss index |
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `embedding_model` | `"moss-minilm"` | `"moss-minilm"` (fast) or `"moss-mediumlm"` (higher accuracy) |
| `alpha` | `0.8` | Hybrid search blend: 1.0 = semantic only, 0.0 = keyword only |
| `auto_refresh` | `False` | Auto-refresh the in-memory index when new docs are added |
| `polling_interval_in_seconds` | `600` | Refresh interval when `auto_refresh=True` |

## How it works

`MossRuntime` implements Agno's `VectorDb` base class:

- **`create()`** — loads an existing index into Moss's in-memory runtime. Call once at startup for fast first queries.
- **`upsert()`** — creates the index on first call, then adds or updates documents. Loads the index automatically after each batch.
- **`search()`** — hybrid semantic + keyword search via the loaded in-memory runtime. Falls back to the cloud API if the index is not loaded.

Moss filters metadata **only when the index is loaded locally**. `content_hash_exists()` returns `False` when unloaded (safe: forces re-upsert rather than silently skipping).

## Choosing a model provider

```python
# OpenAI
from agno.models.openai import OpenAIChat
agent = Agent(model=OpenAIChat(id="gpt-4o"), knowledge=knowledge, search_knowledge=True)

# Anthropic
from agno.models.anthropic import Claude
agent = Agent(model=Claude(id="claude-sonnet-4-20250514"), knowledge=knowledge, search_knowledge=True)
```

See the [Agno model providers docs](https://docs.agno.com/models/introduction) for the full list.

## License

BSD 2-Clause — see [LICENSE](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Agno Docs](https://docs.agno.com)
