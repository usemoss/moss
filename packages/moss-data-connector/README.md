# moss-data-connector

Folder holding the database-connector packages. Each subfolder is its own pip-installable package — no shared core package. One install, one import.

## Layout

```
moss-data-connector/
├── _template/               # copy-me starting point for a new connector
├── moss-connector-sqlite/   # SQLite source (stdlib, no driver)
└── moss-connector-mongodb/  # MongoDB source (requires pymongo)
```

Each package contains its own `ingest.py`. If you change one, change the others too — they should stay the same.

## Caller shape

```python
from moss import DocumentInfo
from moss_connector_sqlite import SQLiteConnector, ingest

source = SQLiteConnector(
    database="my.db",
    query="SELECT id, title, body FROM articles",
    mapper=lambda r: DocumentInfo(id=str(r["id"]), text=r["body"], metadata={"title": r["title"]}),
)

await ingest(source, project_id="...", project_key="...", index_name="articles")
```

One `pip install moss-connector-sqlite` — done.

## Available connectors

| Package                                              | Source   | Extra driver |
| ---------------------------------------------------- | -------- | ------------ |
| [`moss-connector-sqlite`](moss-connector-sqlite)     | SQLite   | —            |
| [`moss-connector-mongodb`](moss-connector-mongodb)   | MongoDB  | `pymongo`    |

## Adding a new connector

See [`_template/README.md`](_template/README.md).

## Credentials for live tests

The two live integration tests (one per connector) read `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` from:

1. `<package>/.env` — per-package override
2. `moss-data-connector/.env` — shared for all connectors (recommended)
3. `<repo-root>/.env`

Put your creds in `moss-data-connector/.env` once and every connector test finds them.
