# Gemma Moss Integration

Moss delivers sub-10ms semantic retrieval for your Gemma-powered chatbot running locally via Ollama.

## Installation

```bash
pip install gemma-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- [Ollama](https://ollama.com/) installed with the Gemma model pulled:

  ```bash
  ollama pull gemma4
  ```

## Quick Start

```python
import asyncio
import os
from gemma_moss import GemmaMossSession, MossRetriever
from gemma_moss.session import make_ollama_query_rewriter

async def main():
    # Set up retriever
    retriever = MossRetriever(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name="my-index",
    )
    await retriever.load_index()

    # Set up session (query rewriter is optional)
    session = GemmaMossSession(
        retriever=retriever,
        model="gemma4",
        query_rewriter=make_ollama_query_rewriter(model="gemma4"),
    )

    # Ask a question
    response = await session.ask("How do refunds work?")
    print(response)

    # Or stream the response
    async for chunk in session.ask_stream("Tell me more"):
        print(chunk, end="")

asyncio.run(main())
```

## Architecture

The package is split into three layers:

### MossRetriever

Reusable retrieval adapter over the Moss SDK. Can be used independently of the session.

```python
retriever = MossRetriever(index_name="my-index")
await retriever.load_index()

# Raw search result
result = await retriever.query("search terms")

# Formatted for LLM context
context = await retriever.retrieve("search terms")
```

### Query Rewriter (Optional)

Any async callable with signature `(message, history) -> str` can serve as a query rewriter. A convenience helper is provided:

```python
from gemma_moss.session import make_ollama_query_rewriter

rewriter = make_ollama_query_rewriter(model="gemma4")
```

### GemmaMossSession

Chat session that composes the retriever and optional rewriter.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `retriever` | (required) | A `MossRetriever` instance |
| `model` | `gemma4` | Ollama model name |
| `ollama_host` | `None` | Ollama server URL |
| `system_prompt` | (see source) | Fixed system prompt |
| `query_rewriter` | `None` | Optional query rewriter callable |
| `history` | `None` | Initial conversation history |

| Method | Description |
|--------|-------------|
| `ask(message)` | Send a message, return full response |
| `ask_stream(message)` | Send a message, stream response tokens |
| `reset()` | Clear conversation history |
| `get_history()` | Return a copy of conversation history |

## Running the Examples

### 1. Create a Moss index (one-time setup)

```bash
export MOSS_PROJECT_ID=your-project-id
export MOSS_PROJECT_KEY=your-project-key
export MOSS_INDEX_NAME=my-faq-index

python examples/moss-create-index-demo.py
```

### 2. Start the chatbot

```bash
python examples/moss-gemma-demo.py
```

Commands: `/reset` (clear history), `/quit` (exit)

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.usemoss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [Ollama Docs](https://ollama.com/docs)
