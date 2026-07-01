# Semantic Kernel Moss Plugin

Moss delivers sub-10ms semantic retrieval, giving your [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/) agents instant access to a knowledge base during conversations.

## Installation

```bash
pip install semantic-kernel-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- Python 3.10+
- A Semantic Kernel [ChatCompletion service](https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/) configured in your kernel

## Quick Start

```python
import asyncio
import os

import semantic_kernel as sk
from semantic_kernel_moss import MossPlugin


async def main():
    # Create and pre-load the Moss plugin
    moss = MossPlugin(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name="my-index",
    )
    await moss.load_index()

    # Register with a Semantic Kernel
    kernel = sk.Kernel()
    kernel.add_plugin(moss, plugin_name="moss")

    # Invoke the search function directly
    result = await kernel.invoke(function_name="search", plugin_name="moss", query="What is your refund policy?")
    print(result)


asyncio.run(main())
```

## Configuration Options

### MossPlugin

| Parameter | Default | Description |
|-----------|---------|-------------|
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `index_name` | (required) | Name of the Moss index to query |
| `top_k` | `5` | Number of results to retrieve per query |
| `alpha` | `0.8` | Blend: 1.0 = semantic only, 0.0 = keyword only |
| `result_prefix` | `Relevant knowledge base results:\n\n` | Prefix for formatted results |

### Methods

| Method | Description |
|--------|-------------|
| `load_index()` | Async. Pre-load the Moss index for fast first queries |
| `search(query)` | Async. Query Moss and return formatted results as a string |

## Using with Chat Completion

Moss works with any Semantic Kernel chat completion service. The kernel can automatically invoke the search function when the LLM decides it needs knowledge base information:

```python
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel_moss import MossPlugin

kernel = sk.Kernel()
kernel.add_service(OpenAIChatCompletion(service_id="chat"))

moss = MossPlugin(index_name="product-docs")
await moss.load_index()
kernel.add_plugin(moss, plugin_name="moss")

result = await kernel.invoke_prompt(
    "Use the moss-search function to answer: {{$input}}",
    input_vars={"input": "What are your shipping options?"},
)
```

## License

This plugin is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [Semantic Kernel Docs](https://learn.microsoft.com/en-us/semantic-kernel/)
