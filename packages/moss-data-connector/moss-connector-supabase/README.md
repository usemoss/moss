# moss-connector-supabase

Supabase source connector for Moss. Uses [supabase-py](https://github.com/supabase/supabase-py) to read rows from a Supabase table over PostgREST.

## Install

```bash
pip install moss-connector-supabase
```

This installs `supabase` automatically.

## Usage

```python
import asyncio
from moss import DocumentInfo
from moss_connector_supabase import SupabaseConnector, ingest

async def main():
    source = SupabaseConnector(
        url="https://xxx.supabase.co",
        key="your-anon-or-service-key",
        table="articles",
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

## Data requirements

The connector doesn't impose a schema — it reads each row as a dict and passes it to your `mapper`. The constraints come from `DocumentInfo`, not the connector.

`DocumentInfo` fields:

| Field | Type | Required? | Typical Supabase column |
|---|---|---|---|
| `id` | `str` | yes | a primary key — `int`, `uuid`, slug, etc. |
| `text` | `str` | yes | the column you want to search (`body`, `description`, `content`...) |
| `metadata` | `Optional[Dict[str, str]]` | no | any other columns you want filterable / displayable |
| `embedding` | `Optional[Sequence[float]]` | no | only if you bring your own vectors with `model_id="custom"` |

So your table needs **at least one stringifiable column** to use as `id` and **at least one text column** to use as `text`. Everything else is optional. Examples:

**Minimal** — `id` + `body`:

```sql
CREATE TABLE notes (id int PRIMARY KEY, body text);
```
```python
mapper=lambda row: DocumentInfo(id=str(row["id"]), text=row["body"])
```

**Rich** — extra columns flow into metadata:

```sql
CREATE TABLE articles (
    id           uuid PRIMARY KEY,
    title        text,
    body         text,
    author       text,
    published_at timestamptz,
    view_count   int,
    tags         text[]
);
```
```python
mapper=lambda row: DocumentInfo(
    id=row["id"],
    text=row["body"],
    metadata={
        "title": row["title"],
        "author": row["author"],
        "published_at": str(row["published_at"]),  # timestamp -> str
        "view_count": str(row["view_count"]),      # int -> str
        "tags": ",".join(row["tags"]),             # array -> joined str
    },
)
```

### One gotcha: metadata values must be strings

Postgres types like `int`, `bool`, `timestamp`, `numeric`, `array`, `jsonb` come back from Supabase as their native Python types (`int`, `bool`, `datetime`, `list`, `dict`). `DocumentInfo.metadata` requires `Dict[str, str]`, so non-string columns must be coerced in the mapper:

```python
# WILL FAIL — non-string values
metadata={"price": row["price"], "in_stock": row["in_stock"]}

# CORRECT
metadata={"price": str(row["price"]), "in_stock": str(row["in_stock"])}
```

The same applies to `id` if your primary key is an `int` — wrap with `str(...)`.

### What you can't do (use a view instead)

- **Joins across tables** — read-from-one-table only. Combine in a Postgres view (`CREATE VIEW articles_with_author AS SELECT a.*, u.name AS author_name FROM articles a JOIN users u ON ...`) and point the connector at the view.
- **Filter rows in Python** — there's no `filter=` kwarg (see [Filtering](#filtering)). Use a view to pre-filter server-side.

## Choosing a key

The `key` argument controls which rows are visible:

- **anon key** — only rows allowed by your Row-Level Security policies. Use this for ingesting publicly readable content.
- **service-role key** — bypasses RLS. Use this for full-table ingest in trusted backend jobs. Never ship a service-role key to a client.

The connector does not enforce this; pick the right key for your use case.

## Filtering

The connector reads every row in the named table. To restrict ingest to a subset, create a Postgres view in Supabase and point the connector at the view:

```sql
CREATE VIEW search_corpus AS
  SELECT id, title, body FROM articles WHERE published = true;
```

```python
SupabaseConnector(table="search_corpus", ...)
```

A `filter=` kwarg is intentionally not exposed in v1 — Supabase's filter API is method-chained and doesn't fit a single-kwarg shape cleanly. If you need parameterized server-side filtering, open an issue.

## Pagination

PostgREST is HTTP-only with no streaming cursor, so the connector pages with `.range(start, end)`. Default `page_size=1000` matches PostgREST's default `db-max-rows` cap. **Do not raise this above your project's server-side cap** — PostgREST silently truncates the response, the connector sees a short page, and stops, missing the rest of the table.

## Layout

```
src/
├── __init__.py      # re-exports SupabaseConnector and ingest
├── connector.py     # SupabaseConnector class
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_supabase.py -v                          # mocked, no network needed
pytest tests/test_integration_supabase_moss.py -v -s      # live Supabase + Moss
```

The integration test requires `SUPABASE_URL`, `SUPABASE_KEY`, `MOSS_PROJECT_ID`, `MOSS_PROJECT_KEY`, and `SUPABASE_TEST_TABLE` (a pre-created table with `id`, `title`, `body` columns; supabase-py can't create tables over PostgREST).
