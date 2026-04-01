# Moss + Smolagents Cookbook

This example shows how to plug **Moss** into a **Smolagents** agent as a blazingly fast retrieval tool.

## 🚀 Why Moss with Smolagents?

When building agents, retrieval steps can really slow things down. Traditional vector databases often take 200–500ms to return results due to round-trips to the cloud. When an agent does multiple tool calls, these delays pile up.

Moss fixes this by letting you load the vector index and model weights directly into your application's memory using `load_index()`. This drops retrieval latency to **under 10ms**, which makes a huge difference in agent responsiveness!

## 📦 Getting Started

1.  **Install the requirements**:
    ```bash
    pip install smolagents inferedge-moss python-dotenv
    ```

2.  **Set up your environment variables**:
    Drop a `.env` file in this folder (or export them directly):
    ```env
    MOSS_PROJECT_ID=your_moss_project_id
    MOSS_PROJECT_KEY=your_moss_project_key
    MOSS_INDEX_NAME=your_moss_index_name
    OPENAI_API_KEY=your_openai_api_key
    ```

## 🛠️ What's happening in the code?

We're subclassing `smolagents.Tool` to create `MossRetrievalTool`. 

We define the schema carefully so the LLM knows how to use it:
- **`name`**: `moss_retrieval`
- **`description`**: Tells the LLM exactly when to grab this tool.
- **`inputs`**: Outlines the `query`, `top_k`, and an optional `metadata_filter`.
- **`forward()`**: This runs the Moss search against the local memory index. 

### The Secret Sauce: Loading the Index

Before we even start the agent, we pull the index into memory:
```python
client = MossClient(project_id, project_key)
asyncio.run(client.load_index("my-docs-index")) # Sub-10ms search unlocked
```
If you skip this step, Moss will fall back to querying the cloud API (which works, but is much slower).

## 🏃 Running the Example

Just run the script:
```bash
python smolagents_retrieval.py
```

You'll see the agent get a question, realize it needs internal docs, call the Moss tool, and write up a grounded answer!
