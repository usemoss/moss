# Using Moss with AutoGen Agents

This cookbook demonstrates how to use **Moss**, a sub-10ms semantic search engine, as a retrieval tool for **AutoGen** agents. 

By integrating Moss, your agents can access large knowledge bases and retrieve relevant context in milliseconds fast enough to keep multi-agent conversations fluid and responsive.

> **Note:** This cookbook uses the modern **AutoGen v0.4.x** API (via the `autogen-agentchat` package).
    
## Prerequisites

Install the necessary libraries:

```bash
pip install autogen-agentchat autogen-ext[openai] inferedge-moss python-dotenv
```

You will also need:
- A Moss **Project ID** and **Project Key** (get them at [moss.dev](https://moss.dev)).
- An **OpenAI API Key**.

## Step 1: Setup Moss Client

First, initialize the Moss client.

```python
import os
from dotenv import load_dotenv
from inferedge_moss import MossClient, DocumentInfo, QueryOptions

load_dotenv()

# Initialize Moss
moss = MossClient(
    project_id=os.getenv("MOSS_PROJECT_ID"),
    project_key=os.getenv("MOSS_PROJECT_KEY"),
)
```

## Step 2: Indexing Knowledge Base

Before searching, we need to add some documents to Moss. In this example, we'll index a few customer support FAQs.

```python
async def setup_kb():
    docs = [
        DocumentInfo(
            id="faq-returns",
            text="Our return policy allows items to be returned within 30 days for a full refund.",
            metadata={"category": "returns"}
        ),
        DocumentInfo(
            id="faq-shipping",
            text="Standard shipping takes 5-7 business days. Priority shipping is 2-3 days.",
            metadata={"category": "shipping"}
        )
    ]
    await moss.create_index("customer_support", docs)

# Run once to initialize
# await setup_kb()
```

## Step 3: Define the Moss Search Tool

Now, we define a tool that the AutoGen agent can call. This function wraps the Moss query.

```python
async def moss_search(query: str, top_k: int = 3) -> str:
    """Search the customer support knowledge base for relevant policies."""
    options = QueryOptions(top_k=top_k)
    
    # Crucial: Moss queries are asynchronous!
    results = await moss.query("customer_support", query, options)
    
    if not results.docs:
        return "No relevant policies found in the knowledge base."
        
    # Format the results for the LLM
    return "\n\n".join([f"[{doc.score:.3f}] {doc.text}" for doc in results.docs])
```

## Step 4: Configure the AutoGen Agent

We'll use the modern `AssistantAgent` from `autogen-agentchat`. We register the `moss_search` function as a tool.

```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Setup the Model Client
model_client = OpenAIChatCompletionClient(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create the Agent
agent = AssistantAgent(
    name="Customer_Support_Assistant",
    model_client=model_client,
    tools=[moss_search],
    system_message="You are a helpful customer support assistant. Use the 'moss_search' tool to look up policies before answering.",
    reflect_on_tool_use=True,
)

# Run a conversation
async def main():
    await Console(agent.run_stream(task="What is your return policy?"))
    await model_client.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Why use Moss for Agents?

1. **Sub-10ms Latency**: Most vector databases add 200-500ms of latency per query. Moss returns results in under 10ms, which is critical when an agent needs to perform multiple searches in a single turn.
2. **Simplified RAG**: No need to manage complex index parameters or chunking services.
3. **Built-in Embeddings**: Moss handles the embedding automatically, so you don't need to call a separate embedding API.
