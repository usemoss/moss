# Moss + Smolagents Cookbook

Use [Moss](https://moss.dev) semantic search as a retrieval tool for [Smolagents](https://huggingface.co/docs/smolagents) agents.

## Why Moss with Smolagents?

Traditional vector databases add 200–500 ms per retrieval hop. Moss loads index and model weights directly into your application process, delivering **sub-10 ms** search — fast enough that the retrieval step disappears from the agent's latency budget.

## Installation

We recommend [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

Or install dependencies directly:

```bash
uv pip install smolagents moss python-dotenv
```

## Setup

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

```env
MOSS_PROJECT_ID=your_project_id
MOSS_PROJECT_KEY=your_project_key
MOSS_INDEX_NAME=your_index_name
```

`HUGGING_FACE_HUB_TOKEN` is needed if the chosen model requires authentication.

## Files

| File | Purpose |
|------|---------|
| `tool.py` | `MossRetrievalTool` — the reusable smolagents `Tool` subclass |
| `moss_smol_agent_demo.py` | End-to-end demo: load index, build agent, run a question |
| `test_integration.py` | Unit tests with mocked Moss client |

## Running the demo

```bash
uv run moss_smol_agent_demo.py
```

## How it works

### Loading the index

The index must be pulled into local memory **once** before the agent starts. This is the step that switches retrieval from cloud-round-trip speed to local speed:

```python
asyncio.run(client.load_index("my-index"))
```

Call this in your setup/startup code, not inside the tool, so the cost is paid once.

### Async / sync bridge

Smolagents' `Tool.forward()` is synchronous, but `MossClient` is async. The tool solves this with a **persistent event loop running in a daemon thread**, started in `__init__`:

```python
self._loop = asyncio.new_event_loop()
self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
self._thread.start()
```

Each `forward()` call submits the coroutine to that loop and blocks until it completes:

```python
asyncio.run_coroutine_threadsafe(coro, self._loop).result()
```

This approach is better than `asyncio.run()` for two reasons:
- **No per-call overhead** — creating and tearing down an event loop on every search would add latency, defeating the purpose of local retrieval.
- **Works in Jupyter / async frameworks** — `asyncio.run()` raises `RuntimeError` when called from an already-running loop; `run_coroutine_threadsafe` does not.

### Metadata filtering

Pass structured filters using the Moss filter DSL:

```python
metadata_filter = {
    "$and": [
        {"field": "category", "condition": {"$eq": "refunds"}},
        {"field": "price", "condition": {"$lt": 50}},
    ]
}
```

Available operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$and`, `$or`.
