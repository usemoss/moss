# Moss + Google ADK Cookbook

Use [Moss](https://moss.dev) semantic search as a high-speed retrieval tool for [Google ADK](https://adk.dev) (Agent Development Kit) agents.

## Why Moss with Google ADK?

Traditional vector databases add 200–500 ms per retrieval hop. Moss loads the index and model weights directly into your application process, delivering **sub-10 ms** search. Because Google ADK natively supports asynchronous tools, it pairs perfectly with Moss's async-first architecture, allowing you to maximize performance.

## Installation

We recommend using [uv](https://docs.astral.sh/uv/) for fast dependency management:

```bash
uv sync
```

Or install dependencies directly:

```bash
uv pip install "google-adk>=1.10.0" moss python-dotenv
```

*Note: This example pins `google-adk>=1.10.0` to ensure optimal parallel execution for async tools.*

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
GEMINI_API_KEY=your_gemini_api_key
```

## Running the demo

```bash
uv run moss_adk_demo.py
```

## How it works

### Loading the index (The Secret Sauce)

The index must be pulled into local memory **once** before the agent starts. This is the step that switches retrieval from standard cloud-round-trip latency to sub-10ms local speed:

```python
await client.load_index("my-index")
```

Call this in your setup/startup code before invoking the ADK agent. If you skip this, Moss will fall back to querying the cloud API (which works, but is significantly slower).

### Native Async Tool

Google ADK natively supports `async def` tool functions. We wrap the `MossClient` in a factory function that returns a fully typed async tool:

```python
def create_moss_tool(client: MossClient, index_name: str):
    async def moss_retrieval(query: str, top_k: int = 5, metadata_filter: dict = None) -> str:
        # ... implementation ...
    return moss_retrieval
```

### Metadata filtering

Google ADK extracts the tool schema from the function signature and docstrings. We document the Moss filter DSL directly in the docstring so Gemini knows how to use it:

```python
metadata_filter = {
    "$and": [
        {"field": "category", "condition": {"$eq": "refunds"}},
        {"field": "price", "condition": {"$lt": 50}},
    ]
}
```

Available operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$and`, `$or`.
