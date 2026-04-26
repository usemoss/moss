# LangGraph + Moss (Groq-backed) Cookbook Example

Use [Moss](https://moss.dev) as the retrieval step inside a [LangGraph](https://www.langchain.com/langgraph) stateful agent graph.

This cookbook keeps the graph intentionally small:

```text
User question -> retrieve node -> generate node -> grounded answer
```

The key detail is that the Moss index is loaded locally with `load_index()` before the graph runs, so retrieval stays in-memory instead of falling back to the cloud API.

## Installation

```bash
cd examples/cookbook/langgraph
pip install -e .
```

## Setup

Copy `.env.example` to `.env` and fill in your values:

```env
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=your-existing-index
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
```

If you do not already have a Moss index for testing, create one with:

```bash
python examples/cookbook/langgraph/create_index.py
```

That script creates a small FAQ-style index with metadata like `category=returns`
so you can test both normal retrieval and the optional filter path. It prints the
exact `MOSS_INDEX_NAME` value to put into `.env`.

We provide a simple equality filter interface (`--filter-eq`) for portability
across shells.

## State Schema

The graph uses a simple typed state:

- `query`: user query passed into the graph
- `metadata_filter`: optional Moss metadata filter dict passed through state
- `top_k`: optional retrieval depth override
- `retrieval_results`: docs written by the `retrieve` node
- `retrieval_context`: formatted context written by the `retrieve` node
- `retrieval_time_ms`: retrieval latency reported by Moss
- `answer`: grounded final answer written by the `generate` node

The `retrieve` node reads `query` and `metadata_filter` from state, calls `client.query()`, and writes the retrieved results back into state for the `generate` node.

## Why `load_index()` Happens First

`moss_langgraph.py` explicitly runs:

```python
await client.load_index(index_name)
```

before compiling and invoking the graph.

That matters because:

- Local loaded index: retrieval stays in-memory, typically around `~1-10ms`
- No local load: `query()` falls back to the cloud API, typically around `~100-500ms`
- Metadata filters are applied on locally loaded indexes, so preloading is the right path for filtered retrieval nodes

## Run It

Single question:

```bash
python examples/cookbook/langgraph/moss_langgraph.py --question "What is the refund policy?"
```

Single question with a metadata filter carried through graph state:

```bash
python examples/cookbook/langgraph/moss_langgraph.py --question "What is the refund policy?" --filter-eq category=returns
```

Interactive loop:

```bash
python examples/cookbook/langgraph/moss_langgraph.py
```

The script loads `.env` from the same directory as `moss_langgraph.py`, so you can run it from the repo root or from inside the example folder.

In interactive mode, each turn lets you optionally provide a metadata filter in `field=value` form before the graph runs.
