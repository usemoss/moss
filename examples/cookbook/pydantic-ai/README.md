# Moss Pydantic AI Cookbook

This cookbook shows how to expose [Moss](https://moss.dev) semantic search as a reusable tool inside a [Pydantic AI](https://ai.pydantic.dev/) agent.

## Overview

Moss is a semantic search platform that delivers sub-10ms retrieval by loading vector indices into local memory. This cookbook provides:

1. **MossSearchTool** — a class that wraps `MossClient` and exposes a `.tool` property for Pydantic AI agents.
2. **as_tool(...)** — a convenience helper that creates the tool in one call.

## Installation

```bash
cd examples/cookbook/pydantic-ai
pip install -e .
```

## Setup

Create a `.env` file in this directory (see `.env.example`):

```env
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=your-index-name
PYDANTIC_AI_MODEL=openai:gpt-4o
OPENAI_API_KEY=your-openai-api-key
```

## Quick Start

### Using MossSearchTool

```python
import asyncio
from moss import MossClient
from pydantic_ai import Agent
from moss_pydantic_ai import MossSearchTool

async def main():
    client = MossClient("your-project-id", "your-project-key")
    moss = MossSearchTool(client=client, index_name="my-index")
    await moss.load_index()                    # pre-load for fast queries

    agent = Agent("openai:gpt-4o", tools=[moss.tool])
    result = await agent.run("What is the refund policy?")
    print(result.output)

asyncio.run(main())
```

### Using the as_tool helper

```python
from moss import MossClient
from moss_pydantic_ai import as_tool

client = MossClient("your-project-id", "your-project-key")
moss, tool = as_tool(client=client, index_name="my-index")
await moss.load_index()

agent = Agent("openai:gpt-4o", tools=[tool])
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | (required) | A `MossClient` instance |
| `index_name` | (required) | Name of the Moss index to query |
| `tool_name` | `moss_search` | Tool name exposed to the LLM |
| `tool_description` | *(auto)* | Tool description exposed to the LLM |
| `top_k` | `5` | Number of results to retrieve per query |
| `alpha` | `0.8` | Blend: 1.0 = semantic only, 0.0 = keyword only |

## Run the Demo

```bash
python moss_pydantic_ai.py
```

The demo creates a `MossClient`, loads your index, defines a `MossSearchTool`, and runs a Pydantic AI agent against it.

## How It Works

Pydantic AI inspects the tool function's signature and docstring to derive the input schema and description. `MossSearchTool._build_tool()` creates an async `moss_search(query: str) -> str` function and wraps it in `pydantic_ai.Tool(...)`, so the parameter schema is auto-generated.

## Files

| File | Description |
|------|-------------|
| `moss_pydantic_ai.py` | `MossSearchTool` class, `as_tool()` helper, and runnable demo |
| `test_integration.py` | Unit tests (mocked, no credentials required) |
| `pyproject.toml` | Package metadata |
| `.env.example` | Template for required environment variables |

## Notes

- This cookbook exposes Moss **search** because that is the concrete capability exposed by the current Python SDK.
- If Moss later adds first-class workflow or action definitions, the same adapter pattern can be promoted into an official `moss.integrations.pydantic_ai` module.
