# Gemma + Moss Integration Design (v2)

## Overview

A Python package, `gemma-moss`, that integrates Moss semantic retrieval with Google's Gemma model running locally via Ollama.

The key design principle: **the LLM decides when to search.** Rather than retrieving from Moss on every turn, the system prompt tells Gemma what is searchable, and Gemma emits a structured search signal (`[SEARCH: ...]`) only when it needs external knowledge. Most turns are a single Ollama call.

The package has two layers:

1. **`MossRetriever`** — A thin reusable retrieval adapter over `inferedge_moss`.
2. **`GemmaMossSession`** — A chat/session wrapper with a single-search-on-demand flow.

## Target Use Case

Primary: terminal-based conversational RAG with a local Gemma model in Ollama and a Moss index.

Secondary: reuse `MossRetriever` directly in scripts, tests, or other integrations without chat/session state.

## Design Goals

- Let the LLM decide when retrieval is needed.
- Keep the Moss layer thin and reusable.
- Keep conversation/session logic separate from retrieval.
- Most turns should be a single Ollama call.
- Support graceful degradation when retrieval yields no results or fails.
- Keep the control-flow protocol strict and minimal.

## Non-Goals

- Multi-search agent loops within a single turn.
- Tool-calling frameworks or generic agent orchestration.
- Token-by-token streaming through the search-decision step.
- Rich retrieval state persisted into chat history.

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

No `inferedge_moss` types are re-exported.

---

## Layer 1: `MossRetriever`

Thin adapter over the Moss SDK. Owns Moss client, index loading, querying, and formatting.

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

### Methods

| Method | Description |
|--------|-------------|
| `async load_index()` | Pre-load the configured Moss index into memory. |
| `async query(query: str) -> SearchResult` | Raw Moss search, returns `SearchResult`. |
| `async retrieve(query: str) -> str \| None` | Search + format. Returns `None` if no docs. |
| `async retrieve_with_result(query: str) -> tuple[SearchResult, str \| None]` | Search, format, return both. Allows caller to inspect doc count. |

### Error Handling

- All query methods raise `RuntimeError` if `load_index()` hasn't been called.
- Moss errors surface directly. Graceful degradation belongs in the session layer.

### `retrieve_with_result` Rationale

The session needs to distinguish "no documents matched" from "retrieval failed" to provide accurate feedback to the LLM. `retrieve()` returns `None` for both empty results and formatter-declined-to-emit, which is ambiguous. `retrieve_with_result()` returns the raw `SearchResult` alongside the formatted text, letting the session inspect `len(result.docs)` for unambiguous three-way outcome resolution.

---

## Formatter Abstraction

```python
class DefaultContextFormatter:
    def __init__(self, *, prefix: str = "Relevant context from knowledge base:\n\n") -> None: ...
    def __call__(self, documents: Sequence[Any]) -> str | None: ...
```

- Returns formatted string when documents are present.
- Returns `None` when document sequence is empty.

---

## Layer 2: `GemmaMossSession`

### How It Works

The system prompt tells Gemma about the Moss index and instructs it to use `[SEARCH: query]` when it needs information.

Per turn:

- **No search signal** → return response directly. 1 Ollama call.
- **Exact `[SEARCH: query]` signal** → one Moss retrieval, then one final Ollama call. 2 Ollama calls.

Exactly one retrieval per turn. No loops.

### Constructor

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

- `system_prompt` — Optional override for the full system prompt. If `None`, a default is built using `index_description`.
- `index_description` — Human-readable description of what's in the index (e.g., "a customer FAQ covering orders, shipping, returns, and payments").
- `history` — Copied on construction, not stored by reference.

### Default System Prompt

```
You are a helpful assistant with access to {index_description}.

When you need information from the knowledge base to answer a question, output ONLY a search request in this exact format:
[SEARCH: your search query here]

Rules:
- Only search when you genuinely need information from the knowledge base.
- Do NOT search for greetings, clarifications, rephrasing requests, or conversational replies.
- When you search, output NOTHING except the single [SEARCH: ...] line.
- If you already have enough information to answer well, answer directly.
- After a search outcome is provided, answer the user's original question.
- If the search finds nothing useful, say so honestly.
- If search is unavailable, say so honestly and answer as best you can.
```

### Public Methods

| Method | Description |
|--------|-------------|
| `async ask(message: str) -> str` | Full turn with optional single retrieval. Returns the final response. |
| `async ask_stream(message: str) -> AsyncIterator[str]` | Thin wrapper over `ask()`. Yields the complete response as one chunk. |
| `reset()` | Clear conversation history. |
| `get_history() -> list[dict[str, str]]` | Return a copy of the conversation history. |

---

## Search Signal Protocol

### Parsing Rule

The entire trimmed model response must match this regex:

```python
_SEARCH_PATTERN = re.compile(r"^\[SEARCH:\s*(.+?)\s*\]$")
```

If it does not match exactly, the response is treated as a final answer. No partial parsing, no substring matching.

---

## Retrieval Outcome Model

Three explicit outcomes after `retriever.retrieve_with_result(query)`:

1. **Context found** — `len(result.docs) > 0` and `context is not None`. Formatted context injected as system message.
2. **No results** — `len(result.docs) == 0`. System message: `"Search completed but no relevant results were found for: {query}"`
3. **Retrieval failed** — Exception raised. System message: `"Search is currently unavailable. Please answer based on your existing knowledge."`

```python
@dataclass(frozen=True)
class _SearchOutcome:
    context: str | None   # formatted context, or None
    note: str | None      # fallback note for no-results or failure
```

The session injects `outcome.context or outcome.note` as the system message before the user message.

---

## Second-Call Search Leak Prevention

The system message for the second Ollama call (after retrieval) includes:

```
A search has already been performed for this turn. Do NOT emit another [SEARCH: ...] request. Answer the user's question directly.
```

Additionally, if the entire trimmed second response matches the search-signal regex again, the session returns a deterministic fallback:

```
I was unable to find a relevant answer. Please try rephrasing your question.
```

No substring stripping. Only triggered on exact full-response match.

---

## Message Assembly

### Initial generation (no search yet):

```python
[
    {"role": "system", "content": system_prompt},
    *history,
    {"role": "user", "content": message},
]
```

### Final generation (after search):

```python
[
    {"role": "system", "content": system_prompt},
    *history,
    {"role": "system", "content": context_or_note + "\n\nA search has already been performed for this turn. Do NOT emit another [SEARCH: ...] request. Answer the user's question directly."},
    {"role": "user", "content": message},
]
```

Retrieved context is ephemeral — NOT persisted in history. Only user + final assistant turns are committed.

---

## Data Flow Per Turn

```
User message
    |
    v
Build messages [system + history + user]
    |
    v
Send to Gemma
    |
    v
Parse response (strict regex)
    |
    +-- No match → Final answer → Commit to history
    |
    +-- Exact [SEARCH: query] match
            |
            v
        Retrieve from Moss via retrieve_with_result()
            |
            v
        Resolve outcome (context / no results / failed)
            |
            v
        Build messages [system + history + outcome + user]
            |
            v
        Send to Gemma → Parse again
            |
            +-- No match → Final answer → Commit to history
            +-- Match again → Return deterministic fallback → Commit to history
```

---

## What Changed from v1

| Aspect | v1 (always-retrieve) | v2 (search-on-demand) |
|--------|---------------------|----------------------|
| Retrieval trigger | Every turn | LLM decides via `[SEARCH:]` |
| Ollama calls per turn | 2 (rewriter + answer) | 1 (most turns) or 2 (when searching) |
| Query rewriter | Separate callable | Removed — LLM generates query itself |
| `make_ollama_query_rewriter` | Exported | Removed |
| `index_description` param | N/A | New — describes what's searchable |
| System prompt | Generic | Includes search instructions |
| Public API exports | 4 classes + inferedge_moss types | 3 classes only |
| `retrieve_with_result()` | N/A | New — unambiguous three-way outcome |

## Dependencies

```toml
[project]
dependencies = [
    "inferedge-moss>=1.0.0b18",
    "ollama>=0.4.0",
]
```

## Conventions

BSD 2-Clause, ruff, Python >=3.10,<3.14, setuptools, src/ layout, stdlib logging.
