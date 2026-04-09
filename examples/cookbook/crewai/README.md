# CrewAI + Moss Cookbook Example

Use [Moss](https://moss.dev) semantic search as a retrieval tool for [CrewAI](https://www.crewai.com/) agents. Agents get sub-10ms search over your knowledge base.

## Installation

```bash
pip install crewai moss python-dotenv
```

## Setup

Set your credentials as environment variables or in a `.env` file (see `.env.example`):

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
GEMINI_API_KEY=your-gemini-key
```

## Quick Start

```python
from crewai import Agent, Task, Crew
from moss import MossClient
from moss_crewai import MossSearchTool

client = MossClient("your-project-id", "your-project-key")

search = MossSearchTool(client=client, index_name="knowledge-base", top_k=5)

researcher = Agent(
    role="Research Assistant",
    goal="Find accurate answers using the knowledge base",
    tools=[search],
)

task = Task(
    description="What are the best budget hotels in Tokyo?",
    expected_output="A concise answer based on the knowledge base.",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
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
| (travel-          |  | (travel-stays)   |  | (travel-          |
|  destinations)    |  |                  |  |  activities)      |
+--------+----------+  +--------+---------+  +---------+---------+
         |                      |                      |
         +----------------------+----------------------+
                                |
                                v
                      +------------------+
                      | Travel Planner   |
                      | (synthesize)     |
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

2. **3 Specialist Agents** each search their Moss index using `MossSearchTool`

3. **Travel Planner Agent** synthesizes all findings into an actionable travel plan

### Run the demo

```bash
cd examples/cookbook/crewai
python example_usage.py
```

```
=== Moss + CrewAI Travel Planner ===
Plan your next trip! Type 'quit' to exit.

You: Plan a 2-day trip to Tokyo on a budget
Agent: ...
```

## Available Tools

All tools are defined in `moss_crewai.py`. Copy this file into your project and import from it.

### Search

| Tool | Agent Input | MossClient Method | Description |
|------|------------|-------------------|-------------|
| `MossSearchTool` | `query: str` | `query()` | Semantic search with ranked results and relevance scores |

**Configuration** (set at construction, not controlled by the agent):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | Shared MossClient instance |
| `index_name` | required | Index to search |
| `top_k` | 5 | Number of results |
| `alpha` | 0.8 | Hybrid search balance (0=keyword, 1=semantic) |

### Document Management

| Tool | Agent Input | MossClient Method | Description |
|------|------------|-------------------|-------------|
| `MossAddDocsTool` | `texts: list[str]`, `ids?: list[str]`, `upsert?: bool` | `add_docs()` | Add documents to an index. Set `upsert=True` to update existing docs. |
| `MossDeleteDocsTool` | `doc_ids: list[str]` | `delete_docs()` | Delete specific documents by their IDs |
| `MossGetDocsTool` | `doc_ids?: list[str]` | `get_docs()` | Retrieve documents. Fetches all if no IDs provided. |

### Index Management

| Tool | Agent Input | MossClient Method | Description |
|------|------------|-------------------|-------------|
| `MossCreateIndexTool` | `index_name: str`, `texts: list[str]`, `ids?: list[str]` | `create_index()` | Create a new index populated with documents |
| `MossDeleteIndexTool` | `index_name: str` | `delete_index()` | Delete an index and all its data (irreversible) |
| `MossGetIndexTool` | `index_name: str` | `get_index()` | Get info about a specific index (doc count, status) |
| `MossListIndexesTool` | *(none)* | `list_indexes()` | List all indexes with doc counts and status |

### moss_tools() Factory

Create all 8 tools with shared configuration:

```python
from moss import MossClient
from moss_crewai import moss_tools

client = MossClient("your-project-id", "your-project-key")
tools = moss_tools(client=client, index_name="knowledge-base")
```

## Files

| File | Description |
|------|-------------|
| `moss_crewai.py` | 8 tool classes + `moss_tools()` factory |
| `example_usage.py` | Multi-agent travel planner CLI demo with 3 specialists and writer |
| `data/` | Travel data: `destinations_moss.json`, `stays_moss.json`, `activities_moss.json` |
| `test_live.py` | Live platform tests against real Moss API |
| `.env.example` | Template for required environment variables |