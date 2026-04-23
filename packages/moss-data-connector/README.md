# moss-data-connector

Folder holding the database-connector packages. Each subfolder is its own pip-installable package

## Layout

```
moss-data-connector/
├── _template/               # copy-me starting point for a new connector
├── moss-connector-sqlite/   # SQLite source (stdlib, no driver)
└── moss-connector-mongodb/  # MongoDB source (requires pymongo)
```


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


## Available connectors

| Package                                              | Source   | Extra driver |
| ---------------------------------------------------- | -------- | ------------ |
| [`moss-connector-sqlite`](moss-connector-sqlite)     | SQLite   | —            |
| [`moss-connector-mongodb`](moss-connector-mongodb)   | MongoDB  | `pymongo`    |

## Adding a new connector

See [`_template/README.md`](_template/README.md).

