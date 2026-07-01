# Google ADK + Moss Cookbook Example

Use [Moss](https://moss.dev) semantic search as a retrieval tool for [Google Agent Development Kit (ADK)](https://adk.dev) agents. Agents get sub-10ms search over your knowledge base.

This example uses OpenAI's GPT models via ADK's built-in [LiteLLM](https://adk.dev/agents/models/litellm/) integration, so you don't need a Gemini/Vertex AI key.

## Installation

```bash
pip install google-adk litellm moss python-dotenv
```

## Setup

Set your credentials as environment variables or in a `.env` file (see `.env.example`):

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
OPENAI_API_KEY=your-openai-api-key
```

## How it works

ADK wraps a plain async function as a tool automatically when it's added to an `Agent`'s `tools` list — the function's name, type hints, and docstring become the schema the model sees. `create_moss_search_tool()` in `moss_adk.py` returns exactly that kind of function, bound to a Moss client and index.

The demo builds an **Onboarding Assistant** that answers new-hire questions (PTO policy, expense reports, laptop setup, benefits, remote work) by searching a small company-handbook index:

```
User Question ("How many vacation days do I get?")
     |
     v
  Onboarding Assistant (Agent, model=openai/gpt-4.1-mini)
     |
     v
  moss_search tool  --->  Moss index ("onboarding-handbook")
     |
     v
  Final Answer, grounded in the handbook
```

## Run the demo

```bash
cd examples/cookbook/google-adk
python moss_adk.py
```

```
You: How many vacation days do I get and how far ahead do I need to request them?

Agent: You accrue 1.5 days of PTO per month (up to 20 days/year), and you should
request time off in Workday at least 5 business days in advance.
```

## Usage in your own agent

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from moss import MossClient
from moss_adk import create_moss_search_tool

client = MossClient("your-project-id", "your-project-key")
search = create_moss_search_tool(client=client, index_name="knowledge-base", top_k=5)

agent = Agent(
    model=LiteLlm(model="openai/gpt-4o-mini"),
    name="research_assistant",
    instruction="Use the moss_search tool to answer questions from the knowledge base.",
    tools=[search],
)
```

`create_moss_search_tool()` takes:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `client` | required | Shared MossClient instance |
| `index_name` | required | Index to search |
| `top_k` | 3 | Number of results |

The returned `moss_search` tool takes a single `query: str` argument from the model and returns a `dict` with a `status` key and either `results` (list of `{id, text, score}`) or a `message`, following ADK's recommended function-tool return convention.

## Files

| File | Description |
|------|-------------|
| `moss_adk.py` | `create_moss_search_tool()` factory + a runnable Onboarding Assistant demo |
| `.env.example` | Template for required environment variables |
