# sim-moss

Moss semantic search integration for [sim.ai](https://sim.ai/) workflows.

Provides `MossSimSearch` — a lightweight adapter that queries a preloaded Moss index and returns documents in sim.ai's expected `{"content", "score", "source"}` shape, ready to be served from a webhook that sim.ai calls as an external tool.

## Installation

```bash
pip install sim-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- Python 3.10+
- A sim.ai workspace with a deployed workflow

## Quick Start

```python
from sim_moss import MossSimSearch

search = MossSimSearch(
    project_id="your-id",
    project_key="your-key",
    index_name="my-docs",
)
await search.load_index()

result = await search.search("How do I reset my password?")
print(result.results)      # [{"content": "...", "score": 0.94, "source": "faq.md"}, ...]
print(result.time_taken_ms)  # 4
```

## Wiring into a sim.ai Workflow

sim.ai workflows can call external HTTP tools. Point an **HTTP tool node** at a webhook server that wraps `MossSimSearch`:

```
POST /search
Body: {"query": "{{user_message}}"}
```

The response shape — `{"results": [...], "time_taken_ms": 4}` — maps directly to sim.ai's tool output. See [examples/cookbook/sim](../../examples/cookbook/sim/) for a complete FastAPI server and setup guide.

## Configuration

### MossSimSearch

| Parameter | Default | Description |
|-----------|---------|-------------|
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `index_name` | (required) | Name of the Moss index to query |
| `top_k` | `5` | Number of results to retrieve per query |
| `alpha` | `0.8` | Blend: 1.0 = semantic only, 0.0 = keyword only |

### Methods

| Method | Description |
|--------|-------------|
| `load_index()` | Async. Pre-load the Moss index — call once at server startup |
| `search(query)` | Async. Query Moss and return a `SimSearchResult` |

### SimSearchResult

| Field | Type | Description |
|-------|------|-------------|
| `results` | `list[dict]` | Documents with `content`, `score`, and optional `source` |
| `time_taken_ms` | `int \| None` | Moss query latency |

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [sim.ai Docs](https://docs.sim.ai)
