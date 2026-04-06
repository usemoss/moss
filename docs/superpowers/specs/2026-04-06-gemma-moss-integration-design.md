# Gemma + Moss Integration Design

## Overview

A Python package, `gemma-moss`, that integrates Moss semantic retrieval with Google's Gemma model running locally via Ollama.

The package is intentionally split into three layers:

1. **`MossRetriever`** — A thin reusable retrieval adapter over `inferedge_moss`.
2. **`QueryRewriter`** — An optional callable that rewrites a user turn into a better retrieval query.
3. **`GemmaMossSession`** — A chat/session wrapper that composes an Ollama chat model, a `MossRetriever`, and an optional `QueryRewriter`.

This keeps retrieval reusable, makes query rewriting optional, and avoids hardwiring one chat strategy into the Moss layer.

## Target Use Case

Primary: terminal-based conversational RAG with a local Gemma model in Ollama and a Moss index.

Secondary: reuse `MossRetriever` directly in scripts, tests, or other integrations without chat/session state.

## Design Goals

- Keep the Moss layer thin and reusable.
- Make query rewriting optional, not structural.
- Keep conversation/session logic separate from retrieval.
- Minimize duplicated prompt-building and result-formatting logic.
- Ensure `ask()` and `ask_stream()` share one internal turn pipeline.
- Allow graceful degradation:
  - If rewriting fails, use the raw user message for retrieval.
  - If retrieval fails, continue generation without retrieved context.
  - If no documents are found, continue generation without retrieved context.

## Package Structure

```
packages/gemma-moss/
├── src/
│   └── gemma_moss/
│       ├── __init__.py           # Public API exports
│       ├── moss_retriever.py     # Moss retrieval adapter
│       ├── formatters.py         # Context formatting helpers
│       └── session.py            # GemmaMossSession
├── examples/
│   ├── moss-gemma-demo.py            # Interactive CLI chatbot
│   └── moss-create-index-demo.py     # One-time index setup helper
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── LICENSE
```

## Public API

`__init__.py` exports:

- `MossRetriever`
- `GemmaMossSession`
- `DefaultContextFormatter`
- `make_ollama_query_rewriter`
- Re-exports from `inferedge_moss`: `MossClient`, `SearchResult`, `DocumentInfo`, `IndexInfo`, `GetDocumentsOptions`

---

## Layer 1: `MossRetriever`

### Responsibility

Own the Moss client, index loading, querying, and formatting of retrieved documents into LLM-ready context text.

### Constructor

```python
class MossRetriever:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        project_key: str | None = None,
        index_name: str,
        top_k: int = 5,
        alpha: float = 0.8,
        formatter: Callable[[Sequence[Any]], str | None] | None = None,
    ) -> None: ...
```

- `project_id` — Moss project ID. Falls back to `MOSS_PROJECT_ID` env var.
- `project_key` — Moss project key. Falls back to `MOSS_PROJECT_KEY` env var.
- `index_name` — Name of the Moss index to query.
- `top_k` — Number of results to retrieve per query.
- `alpha` — Blend between semantic (1.0) and keyword (0.0) scoring.
- `formatter` — Optional callable that formats retrieved docs into a context string. If omitted, uses `DefaultContextFormatter`.

### Methods

| Method | Description |
|--------|-------------|
| `async load_index()` | Pre-load the configured Moss index into memory. |
| `async query(query: str) -> SearchResult` | Raw Moss search, returns `SearchResult`. |
| `async retrieve(query: str) -> str \| None` | Search + format through the configured formatter. Returns `None` if no docs. |

### Error Handling

- If `load_index()` has not been called, `query()` and `retrieve()` raise `RuntimeError`.
- `query()` and `retrieve()` surface Moss errors directly.
- Graceful degradation belongs in the session layer, not the retriever layer.

---

## Formatter Abstraction

### Callable Shape

```python
Callable[[Sequence[Any]], str | None]
```

### Default Formatter

```python
class DefaultContextFormatter:
    def __init__(
        self,
        *,
        prefix: str = "Relevant context from knowledge base:\n\n",
    ) -> None: ...

    def __call__(self, documents: Sequence[Any]) -> str | None: ...
```

- Returns `None` for empty document lists.
- Emits one prefix block followed by one numbered entry per document.
- Includes lightweight metadata when available: `source`, `score`.

---

## Layer 2: Query Rewriter

### Callable Shape

```python
Callable[[str, Sequence[dict[str, str]]], Awaitable[str]]
```

- First argument: the current user message.
- Second argument: prior conversation turns (read-only sequence).

### Failure Semantics

If a rewriter raises an exception or returns an empty string: log a warning, fall back to the raw user message.

### Convenience Helper

```python
def make_ollama_query_rewriter(
    *,
    model: str = "gemma4",
    host: str | None = None,
    instruction: str = (
        "Based on the conversation history and the user's latest message, "
        "generate a concise, specific search query that would retrieve the most "
        "relevant information from a knowledge base. Output ONLY the search query, "
        "nothing else."
    ),
) -> Callable[[str, Sequence[dict[str, str]]], Awaitable[str]]: ...
```

This helper exists to support the target Gemma/Ollama demo ergonomically. It is not part of the core architecture.

---

## Layer 3: `GemmaMossSession`

### Constructor

```python
class GemmaMossSession:
    def __init__(
        self,
        *,
        retriever: MossRetriever,
        model: str = "gemma4",
        ollama_host: str | None = None,
        system_prompt: str = "You are a helpful assistant. Use the provided context to answer questions accurately.",
        query_rewriter: Callable[[str, Sequence[dict[str, str]]], Awaitable[str]] | None = None,
        history: Sequence[dict[str, str]] | None = None,
    ) -> None: ...
```

- `history` is copied on construction (not stored by reference).

### Public Methods

| Method | Description |
|--------|-------------|
| `async ask(message: str) -> str` | Full turn: prepare, generate, commit. Returns complete response. |
| `async ask_stream(message: str) -> AsyncIterator[str]` | Same as `ask` but streams response tokens as they arrive. |
| `reset()` | Clear conversation history for a new session. |
| `get_history() -> list[dict[str, str]]` | Returns a copy of the conversation history. |

### Shared Internal Turn Pipeline

```python
async def _prepare_turn(self, message: str) -> _PreparedTurn: ...
async def _generate_text(self, prepared: _PreparedTurn) -> str: ...
async def _generate_stream(self, prepared: _PreparedTurn) -> AsyncIterator[str]: ...
def _commit_turn(self, message: str, response: str) -> None: ...
def _build_messages(self, *, message: str, context: str | None) -> list[dict[str, str]]: ...
```

`_PreparedTurn` is an internal implementation detail (dataclass/namedtuple holding the built message list).

### `ask()` Flow

1. `prepared = await _prepare_turn(message)`
2. `response = await _generate_text(prepared)`
3. `_commit_turn(message, response)`
4. Return `response`

### `ask_stream()` Flow

1. `prepared = await _prepare_turn(message)`
2. Stream chunks from `_generate_stream(prepared)`, yielding to caller
3. Accumulate full response internally
4. `_commit_turn(message, full_response)` after generation completes

### `_prepare_turn()` Details

1. Resolve retrieval query: if `query_rewriter` is set, call it with `(message, history)`. On failure, fall back to raw `message`.
2. Resolve context: call `retriever.retrieve(resolved_query)`. On failure, log warning, set context to `None`.
3. Build message list via `_build_messages(message=message, context=context)`.
4. Return `_PreparedTurn` with the built messages.

### Message Assembly

```python
[
    {"role": "system", "content": system_prompt},
    *history,
    {"role": "system", "content": context},   # only if context is not None
    {"role": "user", "content": message},
]
```

Retrieved context is ephemeral — it is NOT persisted in history. Only user + assistant turns are committed.

---

## Data Flow Per Turn

```
User message
    |
    v
Prepare turn
    |-- Resolve retrieval query (rewriter or raw)
    |-- Retrieve context from Moss (or None on failure)
    |-- Build final Ollama message list
    v
Generate final answer with Gemma via Ollama
    v
Commit turn (user + assistant to history only)
```

---

## Dependencies

```toml
[project]
name = "gemma-moss"
version = "0.0.1"
description = "Moss semantic search integration with Gemma via Ollama"
readme = "README.md"
requires-python = ">=3.10,<3.14"
dependencies = [
    "inferedge-moss>=1.0.0b18",
    "ollama>=0.4.0",
]

[dependency-groups]
dev = [
    "python-dotenv>=1.2.1",
    "ruff>=0.1.0",
]
```

## CLI Demo (`examples/moss-gemma-demo.py`)

Interactive terminal chatbot:
- Loads env vars from `.env`
- Validates Ollama is running and Gemma model is available
- Loads the Moss index
- Enters a `while True` loop reading user input
- Streams Gemma responses to stdout
- Supports `/reset` to clear history and `/quit` to exit

## Index Setup Helper (`examples/moss-create-index-demo.py`)

Follows the same pattern as `pipecat-moss/examples/moss-create-index-demo.py`:
- Creates a sample FAQ index with demo documents
- Uses `MossClient` directly

## Conventions

- BSD 2-Clause License (matches existing packages)
- Ruff for linting/formatting (same config as other packages)
- Python >=3.10,<3.14
- `setuptools` build backend
- `src/` layout with `find` packages
- Logging via stdlib `logging` (matches elevenlabs-moss pattern)
