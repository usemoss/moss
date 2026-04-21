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
from moss import DocumentInfo
from moss_connectors import ingest
from moss_connectors.connectors.sqlite import SQLiteConnector

async def main():
    source = SQLiteConnector(
        database="./my.db",
        query="SELECT id, title, body FROM articles",
        mapper=lambda r: DocumentInfo(
            id=str(r["id"]),
            text=r["body"],
            metadata={"title": r["title"]},
        ),
    )

    count = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="articles",
    )
    print(f"copied {count} rows")

asyncio.run(main())
```

`ingest()` creates a fresh index from the `DocumentInfo` items the source yields. If an index by that name already exists, Moss will raise — delete it first or pick a new name.

Each connector takes a `mapper` callable that turns one source row (a dict) into a `moss.DocumentInfo`. You decide per-row how columns map onto `id`, `text`, `metadata`, and `embedding`. No config object, no hidden coercion — what you build is what gets uploaded.

### Reusing existing embeddings

If your source already has vectors (Pinecone, Qdrant, Weaviate…), pass them straight through instead of re-embedding:

```python
source = SQLiteConnector(
    database="./my.db",
    query="SELECT id, title, body, vector FROM articles",
    mapper=lambda r: DocumentInfo(
        id=str(r["id"]),
        text=r["body"],
        metadata={"title": r["title"]},
        embedding=r["vector"],       # list[float] goes straight to Moss
    ),
)

await ingest(source, "your_project_id", "your_project_key", index_name="articles")
```

## Available connectors

| Source  | Module                                | Extra      |
| ------- | ------------------------------------- | ---------- |
| SQLite  | `moss_connectors.connectors.sqlite`   | —          |
| MongoDB | `moss_connectors.connectors.mongodb`  | `mongodb`  |

Want Postgres, MySQL, Supabase, Pinecone, etc.? See [CONTRIBUTING.md](CONTRIBUTING.md) — adding one is ~20 lines.

## Running tests

Unit tests (fast, no network, no credentials):

```bash
pip install -e ".[dev]"
pytest tests/test_sqlite.py -v
```

End-to-end against a real Moss project:

```bash
# SQLite -> Moss
# .env must have: MOSS_PROJECT_ID, MOSS_PROJECT_KEY
pytest tests/test_integration_moss.py -v -s

# MongoDB -> Moss (requires a local Mongo at mongodb://localhost:27017;
#   edit MONGODB_URI at the top of the test file to change)
# .env must have: MOSS_PROJECT_ID, MOSS_PROJECT_KEY
pytest tests/test_integration_mongodb_moss.py -v -s
```

Each integration test builds a throwaway source (SQLite DB or a MongoDB database), ingests into a uniquely-named Moss index, runs a real semantic query, and cleans both sides up on exit. Tests auto-skip when their prerequisites aren't met.

## Scope

- **Does**: one-time copy from a database into a Moss index.
- **Doesn't**: parse documents, run on a schedule, sync continuously, sync in both directions.

No auto-discovery, no incremental sync, no CLI — by design.
