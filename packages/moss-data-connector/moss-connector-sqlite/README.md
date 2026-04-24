# moss-connector-sqlite

SQLite source connector for Moss. Self-contained - no separate core package to install.

## Install

```bash
pip install moss-connector-sqlite
```

No driver needed, uses Python's stdlib `sqlite3`.

## Usage

```python
import asyncio
from moss import DocumentInfo
from moss_connector_sqlite import SQLiteConnector, ingest

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

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="articles",
    )
    print(f"copied {result.doc_count} rows")

asyncio.run(main())
```

Use `auto_id=True` when your mapper does not have a stable primary key and you want Moss to generate UUID document IDs.

## Layout

```
src/
├── __init__.py      # re-exports SQLiteConnector and ingest
├── connector.py     # SQLiteConnector class
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_sqlite.py -v              # mocked Moss, no network
pytest tests/test_integration_moss.py -v -s # live Moss (requires MOSS_PROJECT_ID, MOSS_PROJECT_KEY)
```
