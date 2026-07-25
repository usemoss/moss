# moss-connector-postgres

PostgreSQL source connector for Moss. Uses [psycopg](https://www.psycopg.org/psycopg3/) (v3) so it works against regular Postgres, Neon, Supabase (direct URL), CockroachDB, Amazon RDS, Timescale, and pgvector.

## Install

```bash
pip install moss-connector-postgres
```

This installs `psycopg[binary]` automatically.

## Usage

```python
import asyncio
from moss import DocumentInfo
from moss_connector_postgres import PostgresConnector, ingest

async def main():
    source = PostgresConnector(
        dsn="postgresql://user:pass@localhost:5432/mydb",
        query="SELECT id, title, body FROM articles",
        mapper=lambda row: DocumentInfo(
            id=str(row["id"]),
            text=row["body"],
            metadata={"title": row["title"]},
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

### DSN formats

The connector accepts any standard PostgreSQL connection string:

```python
# Local Postgres
PostgresConnector(dsn="postgresql://user:pass@localhost:5432/mydb", ...)

# Neon serverless
PostgresConnector(dsn="postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb", ...)

# Supabase (direct connection URL)
PostgresConnector(dsn="postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres", ...)
```

## Layout

```
src/
├── __init__.py      # re-exports PostgresConnector and ingest
├── connector.py     # PostgresConnector class
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_postgres.py -v                         # mocked, no network or DB needed
pytest tests/test_integration_postgres_moss.py -v -s     # live Postgres + Moss (requires POSTGRES_DSN, MOSS_PROJECT_ID, MOSS_PROJECT_KEY)
```