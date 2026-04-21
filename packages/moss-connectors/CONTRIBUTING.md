# Contributing a connector

A connector is anything you can iterate over that yields one dict per row. Usually that's a class with `__iter__`. Around 20 lines is typical.

## Steps

1. **Copy the template**
   ```bash
   cp templates/new_connector.py src/moss_connectors/connectors/<source>.py
   ```

2. **Accept a `mapper` in `__init__`** and **implement `__iter__`**
   - `__init__` takes `mapper: Callable[[dict[str, Any]], DocumentInfo]` alongside your source-specific config.
   - `__iter__` connects, pulls rows, and yields `self.mapper(row_as_dict)` for each one.
   - Don't pre-filter columns — the caller's mapper decides what to use.

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
- Supabase (`supabase` Python client)
- Snowflake / BigQuery

Comment on the matching GitHub issue if you want to claim one.
