# Moss + Smolagents Cookbook

This example shows how to plug **Moss** into a **Smolagents** agent as a high-performance retrieval tool.

## 🚀 Why Moss with Smolagents?

Retrieval steps are often the bottleneck in agentic workflows. Traditional vector databases can take 200–500ms per search, which leads to slow, unresponsive agents.

Moss solves this by loading the vector index and model weights directly into your application's memory. This enables **sub-10ms** retrieval latency, making your agents feel significantly more responsive.

## 📦 Getting Started

We recommend using [uv](https://docs.astral.sh/uv/) for fast dependency management and execution.

1.  **Install requirements**:
    ```bash
    uv pip install smolagents inferedge-moss python-dotenv
    ```

2.  **Configure environment**:
    Copy the `.env.example` file and fill in your credentials:
    ```bash
    cp .env.example .env
    ```

## 🛠️ Components

The example is split into two main files:

- **`tool.py`**: Contains the `MossRetrievalTool`, a custom `smolagents.Tool` that handles the bridge between the sync agent loop and the async Moss SDK.
- **`moss_smol_agent_demo.py`**: The main entry point that loads the index and runs the agent.

### The Retrieval Tool

The tool defines a clear schema for the LLM:
- **`query`**: The semantic search query.
- **`top_k`**: Number of results to return.
- **`metadata_filter`**: Advanced filtering using the **Moss structured filter DSL**.

#### Moss Filter DSL Example
Moss filters allow for complex combined logic. When the agent uses this tool, it can provide structured filters in this format:
```python
metadata_filter = {
    "$and": [
        {"field": "category", "condition": {"$eq": "refunds"}},
        {"field": "price", "condition": {"$lt": 50}}
    ]
}
```

### Loading the Index

To achieve sub-10ms performance, the index is pulled into local memory once before the agent starts. This is handled in the demo script:
```python
client = MossClient(project_id, project_key)
asyncio.run(client.load_index("my-docs-index"))
```

## 🏃 Running the Demo

```bash
uv run moss_smol_agent_demo.py
```

The agent will receive a question, decide to use the `moss_retrieval` tool, and provide an answer grounded in your local knowledge base.
