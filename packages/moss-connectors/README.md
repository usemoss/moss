# moss-connectors

Copy rows from any database — SQL, NoSQL — into a Moss index.

Status: **alpha**. The shape is intentionally small so the community can add connectors quickly.

> File sources (PDF, DOCX, HTML, Markdown) are **out of scope** — they belong in a separate doc-parsing package.

## Install

```bash
pip install moss-connectors
```

## Usage

```python
import asyncio
from moss import MossClient
from moss_connectors import DocumentMapping, ingest
from moss_connectors.connectors.sqlite import SQLiteConnector

async def main():
    client = MossClient("your_project_id", "your_project_key")

    source = SQLiteConnector(
        database="./my.db",
        query="SELECT id, title, body FROM articles",
    )
    mapping = DocumentMapping(
        id="id",              # which column holds the document id
        text="body",          # which column becomes the indexed text
        metadata=["title"],   # columns copied onto the document as metadata
    )

    count = await ingest(source, mapping, client, index_name="articles")
    print(f"copied {count} rows")

asyncio.run(main())
```

`ingest()` creates a fresh index from the rows it reads. If an index by that name already exists, Moss will raise — delete it first or pick a new name.

Each field in `DocumentMapping` names a column in your source. Whatever's in that column is passed through to Moss as-is. If you need to combine columns or transform values, do it upstream (e.g. in the SQL query itself).

### Reusing existing embeddings

If your source already has vectors (Pinecone, Qdrant, Weaviate…), pass them through instead of re-embedding:

```python
DocumentMapping(
    id="id",
    text="body",
    metadata=["title"],
    embedding="vector",   # column holding a list[float]
)
```

## Available connectors

| Source | Module                               | Extra  |
| ------ | ------------------------------------ | ------ |
| SQLite | `moss_connectors.connectors.sqlite`  | —      |

Want Postgres, MySQL, MongoDB, Supabase, Pinecone, etc.? See [CONTRIBUTING.md](CONTRIBUTING.md) — adding one is ~20 lines.

## Running tests

Unit tests (fast, no network, no credentials):

```bash
pip install -e ".[dev]"
pytest tests/test_sqlite.py -v
```

End-to-end against a real Moss project:

```bash
# Put MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env (see repo root .env.example)
pytest tests/test_integration_moss.py -v -s
```

The integration test creates a uniquely-named index, ingests 5 SQLite rows, runs a real semantic query, and deletes the index on exit. Auto-skipped when the env vars aren't set.

## Scope

- **Does**: one-time copy from a database into a Moss index.
- **Doesn't**: parse documents, run on a schedule, sync continuously, sync in both directions.

No auto-discovery, no incremental sync, no CLI — by design.
