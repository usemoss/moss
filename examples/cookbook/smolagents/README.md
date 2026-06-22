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
| `moss_smolagents.py` | `MossSearchTool` implementation (sync tool wrapping async MossClient) |
| `moss_smol_agent_demo.py` | End-to-end demo: load index, build agent, run a question |
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