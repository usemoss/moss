# Haystack + Moss Cookbook Example

Use [Moss](https://moss.dev) as realtime semantic search in [Haystack](https://haystack.deepset.ai/) RAG pipelines. Moss provides sub-10ms semantic search, Haystack orchestrates the retrieval-to-generation pipeline.

> **Note:** This is a cookbook example, not a packaged integration. `moss_haystack.py` is a self-contained module you can adapt into your own project.

## Installation

```bash
pip install haystack-ai moss python-dotenv
```

## Setup

Set your credentials in a `.env` file (see `.env.example`):

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
GEMINI_API_KEY=your-gemini-key
```

## Quick Start

```python
from haystack import Document
from moss_haystack import MossDocumentStore, MossRetriever

store = MossDocumentStore(index_name="knowledge-base")
store.write_documents([
    Document(id="1", content="I wake up at 6:30 AM on weekdays."),
    Document(id="2", content="Cold showers improve circulation and alertness."),
])

retriever = MossRetriever(document_store=store, top_k=3)
retriever.load_index()
result = retriever.run(query="when do I wake up?")

for doc in result["documents"]:
    print(f"[{doc.score:.2f}] {doc.content}")
```

## Demo: Multi-Index Life Assistant

The included `example_usage.py` runs an interactive CLI life assistant with **keyword-based routing** across two Moss indexes:

```
User Question
     |
     v
Keyword Router
     |
     +-- personal ("my", "I", "me") --> MossRetriever (life-personal)
     |                                        |
     +-- general ("how to", "tips")  --> MossRetriever (life-general)
     |                                        |
     +-- combined (both or neither)  --> Both retrievers → DocumentJoiner
                                              |
                                              v
                                     PromptBuilder → Gemini LLM
                                              |
                                              v
                                        Final Answer
```

### How it works

1. **Two Moss indexes** with synthetic data:
   - `life-personal` (15 docs) — daily routines, fitness schedule, diet, sleep habits
   - `life-general` (15 docs) — tips, research, and advice on health, fitness, productivity

2. **Keyword router** classifies queries:
   - Personal pronouns ("my", "I", "me") → search personal index
   - General keywords ("how to", "benefits", "tips") → search general index
   - Both or neither → search both indexes and join results

3. **Haystack RAG pipeline** retrieves docs → builds prompt → generates answer via Gemini

### Run the demo

```bash
cd examples/cookbook/haystack
python example_usage.py
```

```
=== Life Assistant (Haystack + Moss) ===
Ask about your habits or get general advice.
Type 'quit' to exit.

You: What is my gym routine?
  [Routed to: personal]
Assistant: You go to the gym Monday, Wednesday, and Friday...

You: What are the benefits of cold showers?
  [Routed to: general]
Assistant: Cold exposure therapy benefits include improved circulation...

You: Should I change my morning routine?
  [Routed to: combined]
Assistant: Your current morning routine includes yoga and lemon water...
```

## Components

### MossDocumentStore

Implements Haystack's `DocumentStore` protocol. Creates its own `MossClient` from credentials.

| Method | Description |
|--------|-------------|
| `write_documents(docs, policy)` | Write documents. First call creates the index, subsequent calls upsert. |
| `count_documents()` | Return document count |
| `delete_documents(ids)` | Delete documents by ID |
| `load_index()` | Download index for fast local queries |

### MossRetriever

Haystack `@component` for semantic search.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `document_store` | required | MossDocumentStore instance |
| `top_k` | 5 | Number of results |
| `alpha` | 0.8 | Hybrid search balance (0=keyword, 1=semantic) |

| Method | Description |
|--------|-------------|
| `load_index()` | Load Moss index for fast local queries |
| `run(query, top_k)` | Search and return `{"documents": list[Document]}` |

## Files

| File | Description |
|------|-------------|
| `moss_haystack.py` | MossDocumentStore + MossRetriever implementation |
| `example_usage.py` | Multi-index life assistant with keyword routing |
| `data/` | Synthetic data: `personal_habits.json`, `general_knowledge.json` |
| `test_live.py` | Live platform tests |
| `.env.example` | Template for required environment variables |
