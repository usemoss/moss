# Moss Python Examples

These examples show how to search through an index using the Moss Python SDK.

## Setup

1. Create and activate a virtual environment:

   ```bash
   uv venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Create a `.env` file in the root of the project (copy from `.env.example`) and fill in your credentials:

   ```env
   MOSS_PROJECT_ID=your-project-id
   MOSS_PROJECT_KEY=your-project-key
   ```

## Files

### simple_quickstart.py

Loads an index and runs a basic search query. Good starting point.

```bash
python simple_quickstart.py
```

### advance_query.py

Same as the simple example but with extra options:

- `top_k` — how many results to return
- `alpha` — controls the balance between keyword and semantic search (0 = keyword only, 1 = semantic only)
- `filter` — narrows results by metadata (e.g. only show documents in the `returns` category)

```bash
python advance_query.py
```

## What the output looks like

```text
Index loaded successfully.
  ID: doc-42
  Text: You can return damaged products within 30 days...
  Score: 0.91
  Metadata: {'category': 'returns'}
```

## Resources

- [Docs](https://docs.moss.dev/?utm_source=github&utm_medium=readme&utm_campaign=python-examples)
- [Portal](https://portal.usemoss.dev/?utm_source=github&utm_medium=readme&utm_campaign=python-examples)
- [GitHub](https://github.com/usemoss/moss)
- [Discord](https://discord.com/invite/eMXExuafBR?utm_source=github&utm_medium=readme&utm_campaign=python-examples)
