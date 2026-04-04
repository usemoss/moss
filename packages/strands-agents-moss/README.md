# Strands Agents Moss Integration

Moss delivers sub-10ms semantic retrieval, giving your [Strands Agents](https://strandsagents.com) instant access to a knowledge base during conversations.

## Installation

```bash
pip install strands-agents-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- Python 3.10+
- **Model provider credentials** — Strands Agents defaults to [Amazon Bedrock](https://aws.amazon.com/bedrock/) as the LLM provider. Make sure your AWS credentials are configured (e.g. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`). To use a different provider, see [Choosing a model provider](#choosing-a-model-provider) below.

## Quick Start

```python
import asyncio
import os

from strands import Agent
from strands_agents_moss import MossSearchTool

async def main():
    # Create and pre-load the Moss search tool
    moss = MossSearchTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name="my-index",
    )
    await moss.load_index()

    # Create a Strands agent with Moss retrieval
    agent = Agent(tools=[moss.tool])
    agent("What is your refund policy?")

asyncio.run(main())
```

## Choosing a Model Provider

Strands Agents defaults to **Amazon Bedrock**. If you don't have AWS credentials or prefer a different provider, pass a `model` argument to `Agent`:

```python
# OpenAI
from strands.models.openai import OpenAIModel
agent = Agent(model=OpenAIModel("gpt-4o"), tools=[moss.tool])

# Anthropic
from strands.models.anthropic import AnthropicModel
agent = Agent(model=AnthropicModel("claude-sonnet-4-20250514"), tools=[moss.tool])
```

See the [Strands model providers docs](https://strandsagents.com/latest/user-guide/concepts/model-providers/overview/) for all supported providers.

## Configuration Options

### MossSearchTool

| Parameter | Default | Description |
|-----------|---------|-------------|
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `index_name` | (required) | Name of the Moss index to query |
| `tool_name` | `moss_search` | Tool name exposed to the LLM |
| `tool_description` | *(auto-generated)* | Tool description exposed to the LLM |
| `top_k` | `5` | Number of results to retrieve per query |
| `alpha` | `0.8` | Blend: 1.0 = semantic only, 0.0 = keyword only |
| `result_prefix` | `Relevant knowledge base results:\n\n` | Prefix for formatted results |

### Methods

| Method | Description |
|--------|-------------|
| `load_index()` | Async. Pre-load the Moss index for fast first queries |
| `search(query)` | Async. Query Moss and return formatted results as a string |
| `tool` | Property. Returns the Strands-compatible tool to pass to `Agent(tools=[...])` |

## Multi-Agent Example

Moss tools work seamlessly with Strands' agents-as-tools pattern:

```python
from strands import Agent
from strands_agents_moss import MossSearchTool

async def main():
    moss = MossSearchTool(
        index_name="product-docs",
    )
    await moss.load_index()

    # Research agent with knowledge base access
    researcher = Agent(
        system_prompt="You are a research assistant. Use moss_search to find information.",
        tools=[moss.tool],
    )

    # Orchestrator that delegates to the researcher
    orchestrator = Agent(
        system_prompt="You coordinate research tasks. Delegate questions to the researcher.",
        tools=[researcher.as_tool(
            name="researcher",
            description="A research assistant with access to the knowledge base",
        )],
    )

    orchestrator("Summarize our return and refund policies.")
```

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [Strands Agents Docs](https://strandsagents.com/latest/)
