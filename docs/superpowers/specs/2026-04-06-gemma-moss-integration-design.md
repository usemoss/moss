# Gemma 4 + Moss Integration Design

## Overview

A Python package (`gemma-moss`) that integrates Moss semantic search with Google's Gemma 4 model running locally via Ollama. It provides a conversational RAG adapter with an agent-driven query generation step — Gemma 4 first reformulates the user's question into an optimized search query, retrieves relevant context from Moss, then generates the final response.

## Target Use Case

CLI chatbot: terminal-based Q&A where a user chats with Gemma 4 and it intelligently retrieves from a Moss index to ground its answers.

## Package Structure

```
packages/gemma-moss/
├── src/
│   └── gemma_moss/
│       ├── __init__.py              # Public API: MossGemmaChat, re-exports from inferedge_moss
│       └── moss_gemma_chat.py       # Core adapter class
├── examples/
│   ├── moss-gemma-demo.py           # Interactive CLI chatbot
│   └── moss-create-index-demo.py    # One-time index setup helper
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## Core Class: `MossGemmaChat`

### Constructor

```python
MossGemmaChat(
    *,
    project_id: str | None = None,       # Falls back to MOSS_PROJECT_ID env var
    project_key: str | None = None,      # Falls back to MOSS_PROJECT_KEY env var
    index_name: str,                     # Required: Moss index to query
    model: str = "gemma4",               # Ollama model name
    ollama_host: str | None = None,      # Defaults to http://localhost:11434
    top_k: int = 5,                      # Number of Moss results per query
    alpha: float = 0.8,                  # Semantic vs keyword blend (1.0 = pure semantic)
    system_prompt: str = "You are a helpful assistant. Use the provided context to answer questions accurately.",
    retrieval_prefix: str = "Relevant context from knowledge base:\n\n",
)
```

### Methods

| Method | Description |
|--------|-------------|
| `async load_index()` | Pre-load the Moss index into memory for fast queries. Must be called before `ask`/`ask_stream`. |
| `async ask(message: str) -> str` | Send a user message. Internally: (1) generate search query via Gemma, (2) retrieve from Moss, (3) return full response. |
| `async ask_stream(message: str) -> AsyncIterator[str]` | Same as `ask` but streams response tokens. |
| `reset()` | Clear conversation history for a new session. |

### Internal: `_generate_search_query(message: str) -> str`

A lightweight Ollama call that sends the conversation history + current user message with a system instruction:

> "Based on the conversation history and the user's latest message, generate a concise, specific search query that would retrieve the most relevant information from a knowledge base. Output ONLY the search query, nothing else."

This accounts for:
- Pronoun resolution from conversation history
- Stripping filler words
- Expanding abbreviations
- Rephrasing for better semantic match

### Internal: `_retrieve_context(query: str) -> str | None`

Queries the Moss index with the generated search query. Returns formatted results string or `None` if no results. On failure, logs a warning and returns `None` (graceful degradation).

## Data Flow (Per Turn)

```
User message
    |
    v
[Call 1] Gemma 4 generates optimized search query
    |
    v
Moss semantic search with refined query
    |
    v
Format results as context string
    |
    v
Build message list:
  1. System prompt (fixed)
  2. Conversation history (prior user + assistant turns)
  3. Retrieved context as system message (ephemeral, not persisted)
  4. Current user message
    |
    v
[Call 2] Gemma 4 generates final response (streamed)
    |
    v
Append user message + assistant response to history
```

Key behaviors:
- Two Ollama calls per turn: one lightweight (query gen), one full (answer gen)
- Retrieved context is injected as a system message right before the user message, NOT persisted in history (prevents context bloat)
- If Moss returns no results, the answer call proceeds without extra context
- If Moss query fails, log warning and proceed without retrieval
- Conversation history is maintained in-memory across turns
- `reset()` clears history

## Dependencies

```toml
[project]
dependencies = [
    "inferedge-moss>=1.0.0b18",
    "ollama>=0.4.0",
]
```

Dev dependencies: `python-dotenv`, `ruff`

## CLI Demo (`examples/moss-gemma-demo.py`)

Interactive terminal chatbot:
- Loads env vars from `.env`
- Validates Ollama is running and Gemma 4 model is available
- Loads the Moss index
- Enters a `while True` loop reading user input
- Streams Gemma 4 responses to stdout
- Supports `/reset` to clear history and `/quit` to exit

## Index Setup Helper (`examples/moss-create-index-demo.py`)

Follows the same pattern as `pipecat-moss/examples/moss-create-index-demo.py`:
- Creates a sample FAQ index with demo documents
- Uses `MossClient` directly

## README Structure

Follows the same format as `elevenlabs-moss` and `pipecat-moss` READMEs:
- Installation instructions
- Prerequisites (Moss credentials, Ollama with Gemma 4)
- Usage code snippet
- Configuration options table
- Running the example
- License and support links

## Conventions

- BSD 2-Clause License (matches existing packages)
- Ruff for linting/formatting (same config as other packages)
- Python >=3.10,<3.14
- `setuptools` build backend
- `src/` layout with `find` packages
- Logging via stdlib `logging` (not loguru — matches elevenlabs-moss pattern)
