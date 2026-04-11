# OpenAI Agents SDK + Moss Cookbook Example

Use [Moss](https://moss.dev) semantic search as a retrieval tool for [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) agents. Agents get sub-10ms search over your knowledge base.

## Installation

```bash
pip install openai-agents moss python-dotenv
```

## Setup

Set your credentials as environment variables or in a `.env` file (see `.env.example`):

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
OPENAI_API_KEY=your-openai-key
```

## Quick Start

```python
import asyncio
from agents import Agent, Runner
from moss import MossClient
from moss_openai_agents import moss_search_tool

client = MossClient("your-project-id", "your-project-key")
search = moss_search_tool(client=client, index_name="knowledge-base", top_k=5)

agent = Agent(
    name="Research Assistant",
    instructions="Find accurate answers using the knowledge base.",
    tools=[search],
)

async def main():
    result = await Runner.run(agent, input="What are the best budget hotels in Tokyo?")
    print(result.final_output)

asyncio.run(main())
```

## Demo: Multi-Agent Travel Planner

The included `example_usage.py` runs an interactive CLI travel planner with **4 agents**:

```
User Question (e.g. "Plan a 2-day trip to Tokyo on a budget")
     |
     v
+-------------------+  +------------------+  +-------------------+
| Destinations      |  | Hotels & Stays   |  | Activities &      |
| Specialist        |  | Specialist       |  | Tours Specialist  |
+--------+----------+  +--------+---------+  +---------+---------+
         \                      |                      /
          +---------------------+---------------------+
                                |
                                v
                      +------------------+
                      | Travel Planner   |
                      | (orchestrator)   |
                      +------------------+
                                |
                                v
                          Final Answer
```

### How it works

1. **Setup**: Travel data is indexed into 3 Moss indexes:
   - `travel-destinations` (10 docs) — city guides, budget tips, transport, best times to visit
   - `travel-stays` (11 docs) — hotels, hostels, prices, amenities
   - `travel-activities` (24 docs) — tours, sightseeing, dining, experiences with costs

2. **3 Specialist Agents** each search their Moss index via `moss_search` function tool

3. **Travel Planner Agent** uses `agent.as_tool()` to delegate to specialists, then synthesizes findings

### Run the demo

```bash
cd examples/cookbook/openai-agents
pip install -e .
python example_usage.py
```

```
=== Moss + OpenAI Agents SDK Travel Planner ===
Plan your next trip! Type 'quit' to exit.

You: Plan a 2-day trip to Tokyo on a budget
Agent: ...
```

## Available Tools

All tools are defined in `moss_openai_agents.py`. Import the factory functions and pass the returned tools to your agent.

### Search

| Factory Function | Agent Input | Description |
|-----------------|------------|-------------|
| `moss_search_tool(client, index_name)` | `query: str` | Semantic search with ranked results and relevance scores |
| `moss_search_with_filter_tool(client, index_name)` | `query: str`, `filter_field?: str`, `filter_value?: str` | Search with optional metadata filtering |

**Configuration** (set at construction, not controlled by the agent):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | Shared MossClient instance |
| `index_name` | required | Index to search |
| `top_k` | 5 | Number of results |
| `alpha` | 0.8 | Hybrid search balance (0=keyword, 1=semantic) |

### Document Management

| Factory Function | Agent Input | Description |
|-----------------|------------|-------------|
| `moss_add_docs_tool(client, index_name)` | `texts: list[str]`, `ids?: list[str]`, `upsert?: bool` | Add documents to an index |
| `moss_delete_docs_tool(client, index_name)` | `doc_ids: list[str]` | Delete specific documents by their IDs |
| `moss_get_docs_tool(client, index_name)` | `doc_ids?: list[str]` | Retrieve documents (all if no IDs) |

### Index Management

| Factory Function | Agent Input | Description |
|-----------------|------------|-------------|
| `moss_list_indexes_tool(client)` | *(none)* | List all indexes with doc counts and status |

### moss_tools() Factory

Create all 6 tools with shared configuration:

```python
from moss import MossClient
from moss_openai_agents import moss_tools

client = MossClient("your-project-id", "your-project-key")
tools = moss_tools(client=client, index_name="knowledge-base")

agent = Agent(name="Assistant", tools=tools)
```

## Metadata Filters

Use `moss_search_with_filter_tool` when your documents have metadata fields you want to filter on:

```python
from moss_openai_agents import moss_search_with_filter_tool

search = moss_search_with_filter_tool(client=client, index_name="travel-destinations")

agent = Agent(
    name="Japan Specialist",
    instructions="Search for travel info. Use filter_field='country' and filter_value='Japan' to narrow results.",
    tools=[search],
)
```

## Local vs Cloud Speed

Moss supports loading indexes locally for sub-10ms retrieval:

- **Cloud query** (default): ~50-200ms — data stays on Moss servers
- **Local query** (after `load_index()`): ~1-10ms — index loaded into memory

All tools in this cookbook call `load_index()` automatically before the first search. For latency-sensitive applications, ensure `load_index()` completes before serving requests.

## Files

| File | Description |
|------|-------------|
| `moss_openai_agents.py` | 6 tool factory functions + `moss_tools()` helper |
| `example_usage.py` | Multi-agent travel planner CLI demo |
| `data/` | Travel data: `destinations_moss.json`, `stays_moss.json`, `activities_moss.json` |
| `test_live.py` | Live platform tests against real Moss API |
| `.env.example` | Template for required environment variables |
