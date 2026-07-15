# Moss Langflow Cookbook

This cookbook provides drag-and-drop [Moss](https://moss.dev) retrieval components for [Langflow](https://github.com/langflow-ai/langflow).

## Overview

Moss is a sub-10 ms semantic search runtime. These Langflow custom components let visual-builder users add Moss retrieval to their flows **without writing code**.

Two components are included:

1. **Moss Retriever** — returns structured `Data` objects (text, score, metadata) for downstream pipeline use.
2. **Moss Search** — returns formatted text ready for direct LLM prompt injection.

## Installation

### Option A: Paste into Langflow (quickest)

1. Open Langflow and create a new flow.
2. Add a **Custom Component** node to the canvas.
3. Open the code editor and paste the contents of [`moss_langflow.py`](moss_langflow.py).
4. The component will appear with configurable inputs.

### Option B: Install as a package

```bash
pip install langflow-moss
```

Or install from source:

```bash
cd examples/cookbook/langflow
pip install -e .
```

The components will be available in Langflow's component sidebar after restart.

## Setup

You need a Moss project. Sign up at [moss.dev](https://moss.dev) to get your credentials (free tier available).

Configure credentials either:

- **In the component UI**: Fill in the *Moss Project ID* and *Moss Project Key* fields directly.
- **Via environment variables**: Set `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` before starting Langflow.

```bash
cp .env.example .env
# Edit .env with your credentials
```

## Component Reference

### Moss Retriever

Returns a list of `Data` objects, each containing:

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Document content |
| `score` | `float` | Relevance score (0–1) |
| `id` | `str` | Document ID |
| `metadata` | `dict` | Document metadata |

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| Moss Project ID | Text | `$MOSS_PROJECT_ID` | Your Moss project ID |
| Moss Project Key | Secret | `$MOSS_PROJECT_KEY` | Your Moss project key (masked in UI) |
| Index Name | Text | *(required)* | Name of the Moss index to query |
| Search Query | Text | *(required)* | The search query text |
| Top K | Integer | `5` | Number of results to return |
| Alpha (Hybrid Search) | Float | `0.5` | 0.0 = keyword, 1.0 = semantic, 0.5 = balanced |
| Metadata Filter (JSON) | Text | *(empty)* | Advanced: Moss filter as JSON |

### Moss Search

Returns a `Message` with formatted text like:

```
Result 1 (score: 0.923):
Refunds are processed within 3-5 business days.

Result 2 (score: 0.847):
You can track your order on the dashboard.
```

Same inputs as the Moss Retriever.

## Example Flow

A typical RAG flow in Langflow:

```
[Chat Input] → [Moss Retriever] → [Prompt Builder] → [OpenAI LLM] → [Chat Output]
```

1. **Chat Input**: User asks a question.
2. **Moss Retriever**: Searches your knowledge base with sub-10 ms latency.
3. **Prompt Builder**: Combines the retrieved documents with the user's question.
4. **OpenAI LLM**: Generates an answer grounded in the retrieved context.
5. **Chat Output**: Returns the answer to the user.

Alternatively, use the **Moss Search** component to get pre-formatted text and wire it directly into a prompt template.

## Advanced: Metadata Filtering

Use the *Metadata Filter (JSON)* input to narrow results:

```json
{"$eq": {"category": "faq"}}
```

```json
{"$and": [{"$eq": {"department": "support"}}, {"$eq": {"language": "en"}}]}
```

See [Moss metadata filtering docs](https://docs.moss.dev/docs/integrate/metadata-filtering) for the full filter syntax.

## Related

- [Moss Documentation](https://docs.moss.dev)
- [Moss Python SDK](https://pypi.org/project/moss/)
- [Langflow Documentation](https://docs.langflow.org)
- [LangChain Cookbook](../langchain/) — if you prefer code-first LangChain integration
