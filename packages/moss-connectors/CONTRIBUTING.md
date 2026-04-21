# Contributing a connector

A connector is anything you can iterate over that yields one dict per row. Usually that's a class with `__iter__`. Around 20 lines is typical.

## Steps

1. **Copy the template**
   ```bash
   cp templates/new_connector.py src/moss_connectors/connectors/<source>.py
   ```

2. **Implement `__iter__`**
   - Connect to the source using its driver.
   - Yield one `dict` per row.
   - Each dict must include the id column named by `DocumentMapping.id`.
   - Return everything — don't pre-filter. The caller's `DocumentMapping` decides what becomes text/metadata.

3. **Declare the driver as an optional dep** in [pyproject.toml](pyproject.toml):
   ```toml
   [project.optional-dependencies]
   mysource = ["my-driver>=1.0"]
   ```
   Import the driver *inside* your connector module, not at the top of the package, so users who install a different extra don't pay the import cost.

4. **Write a test** — mirror [tests/test_sqlite.py](tests/test_sqlite.py). The `FakeMossClient` pattern there avoids network calls. If your source is hard to spin up, contribute a docker-compose fixture under `tests/fixtures/`.

   > Moss stores embeddings as `float32`. When asserting on an embedding value, use `pytest.approx(..., rel=1e-6)` — exact `==` against `float64` literals will fail.

5. **Add a row to the table in [README.md](README.md)** and open a PR.

## Rules

- **One file per connector.**
- **No shared base class.** If you think two connectors need one, they probably don't — a base class here ends up getting in the way.
- **Synchronous iteration.** `ingest()` handles the async calls to Moss. If your driver is async-only, wrap it with `asyncio.run()` inside your class.
- **No retries or rate-limit logic in the core.** If a connector needs it, put it inside that connector.

## Good first connectors

- Postgres (`psycopg`)
- MySQL (`pymysql`)
- MongoDB (`pymongo`)
- Supabase (`supabase` Python client)
- Snowflake / BigQuery

Comment on the matching GitHub issue if you want to claim one.
