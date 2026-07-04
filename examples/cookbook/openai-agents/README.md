# OpenAI Agents + Moss Cookbook

This cookbook shows how to use [Moss](https://docs.moss.dev) semantic search as
a local function tool inside the
[OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python).

The example loads a Moss index before the agent runs, exposes a `moss_search`
tool with `query`, `top_k`, and `filter` arguments, and returns structured
retrieval results that the agent can use to answer a support question.

## Requirements

- Python 3.10+
- A Moss project with `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`
- An index name in `MOSS_INDEX_NAME`
- An OpenAI API key in `OPENAI_API_KEY`

## Installation

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment Setup

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

```env
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=your-index-name
OPENAI_API_KEY=your-openai-api-key
```

`example.py` validates all four variables before creating the Moss client or
running the OpenAI agent.

## Demo Index

On startup, the script checks whether `MOSS_INDEX_NAME` already exists. If it
does, the existing index is reused. If not, the script creates a small support
index with password reset, refund policy, and support-hours documents.

The demo documents include metadata such as `category` and `region` so metadata
filters can be tried immediately after the index is created.

## Local Index Loading

The example explicitly calls:

```python
await client.load_index(index_name)
```

before `Runner.run(...)`.

Loading the index places it in the Moss local runtime. Once loaded, queries avoid
a network hop on the query hot path and can use local metadata filtering. Without
a locally loaded index, `MossClient.query()` may use its documented cloud
fallback behavior. Actual latency depends on index size, machine resources,
network conditions, and whether the local model/index cache is already warm.

## Run the Example

```bash
python example.py
```

The script asks:

```text
How long do refunds take to process?
```

Expected behavior:

1. Moss creates or reuses the demo index.
2. Moss loads the index into the local runtime.
3. The OpenAI agent calls `moss_search`.
4. The tool returns JSON with matching document IDs, text, scores, and metadata.
5. The agent returns an answer grounded in those retrieved documents.

## Tool Arguments

The OpenAI Agents SDK derives the public tool schema from the decorated function:

```python
async def moss_search(
    query: str,
    top_k: int = 3,
    filter: dict[str, Any] | None = None,
) -> str:
    ...
```

- `query`: Natural-language lookup text.
- `top_k`: Number of Moss results to return. The cookbook accepts `1` through
  `20` and defaults to `3`.
- `filter`: Optional Moss metadata filter passed directly to
  `QueryOptions(filter=...)`.

## Metadata Filters

Use metadata filters when the question should be constrained to a known slice of
the index, such as product category, region, customer segment, document source,
or publication date bucket. Filters are especially useful when the same index
contains similar documents for different audiences or workflows.

Equality filter:

```python
filter = {"field": "category", "condition": {"$eq": "policy"}}
```

Compound filter:

```python
filter = {
    "$and": [
        {"field": "category", "condition": {"$eq": "policy"}},
        {"field": "region", "condition": {"$eq": "global"}},
    ]
}
```

Other supported operators in the Moss Python examples and tests include `$ne`,
`$gt`, `$lt`, `$gte`, `$lte`, `$in`, `$nin`, `$or`, nested `$and`/`$or`, and
`$near` for location-style metadata.

## Testing

The unit tests mock Moss and OpenAI Agents SDK objects. They do not require real
credentials or network calls.

```bash
python -m unittest test_example.py
python -m py_compile example.py test_example.py
ruff check example.py test_example.py
black --check example.py test_example.py
```

## Troubleshooting

- Missing credentials: ensure `.env` exists and contains `MOSS_PROJECT_ID`,
  `MOSS_PROJECT_KEY`, `MOSS_INDEX_NAME`, and `OPENAI_API_KEY`.
- Missing index: the demo creates a small index if `MOSS_INDEX_NAME` is not
  found. If creation fails, check that the Moss project credentials can create
  indexes.
- Slow first run: the first `load_index()` call may need to download index data
  or local model assets. Later runs can be faster once caches are warm.
- Filter returns no results: confirm the documents in the index have metadata
  keys and values matching the filter exactly.
