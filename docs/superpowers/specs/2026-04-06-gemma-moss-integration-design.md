# Gemma + Moss Integration Design (v3)

## Overview

A Python package, `gemma-moss`, that integrates Moss semantic retrieval with Google's Gemma model running locally via Ollama using **native tool calling**.

Gemma gets Moss registered as a tool. It calls it when it needs information, doesn't when it doesn't. No custom protocols, no signal parsing. Just Ollama's built-in tool-calling API.

## Layers

1. **`MossRetriever`** — Thin reusable retrieval adapter over `inferedge_moss`. Unchanged.
2. **`GemmaMossSession`** — Chat session that registers Moss as an Ollama tool and handles tool-call responses.

## How It Works

1. User sends a message.
2. Session sends message to Gemma via Ollama with Moss search registered as a tool.
3. Gemma either:
   - **Responds directly** (no tool call) → done. 1 Ollama call.
   - **Calls the `search_knowledge_base` tool** → session executes the Moss query, sends results back to Gemma → Gemma responds. 2 Ollama calls.
4. Only user + final assistant turns are persisted to history.

## `GemmaMossSession` Constructor

```python
class GemmaMossSession:
    def __init__(
        self,
        *,
        retriever: MossRetriever,
        model: str = "gemma4",
        ollama_host: str | None = None,
        system_prompt: str | None = None,
        index_description: str = "a knowledge base",
        history: Sequence[dict[str, str]] | None = None,
    ) -> None: ...
```

## Tool Definition

Registered with every Ollama chat call:

```python
MOSS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "Search {index_description} for relevant information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant information.",
                }
            },
            "required": ["query"],
        },
    },
}
```

## Default System Prompt

```
You are a helpful assistant with access to {index_description}.
Use the search_knowledge_base tool when you need information from the knowledge base.
Do not search for greetings or conversational replies.
```

## Turn Flow

```
User message
    |
    v
Send to Ollama with tool definition
    |
    v
Response type?
    |
    +-- No tool call → Final answer → Commit to history
    |
    +-- tool_call: search_knowledge_base(query)
            |
            v
        retriever.retrieve(query)
            |
            v
        Send tool result back to Ollama
            |
            v
        Gemma answers with context → Commit to history
```

## Graceful Degradation

- Retrieval fails → send tool result: "Search is currently unavailable."
- No results → send tool result: "No relevant results found."
- Gemma answers based on whatever it gets.

## Public API

- `MossRetriever`
- `GemmaMossSession`
- `DefaultContextFormatter`

## What Changed from v1/v2

| Aspect | v1 | v2 | v3 |
|--------|----|----|-----|
| Mechanism | Always retrieve + rewriter | Custom [SEARCH:] protocol | Ollama native tool calling |
| Complexity | Medium | High | Low |
| LLM decides | No | Yes (in-band) | Yes (native) |
| Lines of session code | ~200 | ~250 | ~100 |
