# moss-connector-zeroentropy

ZeroEntropy source connector for Moss. Uses the [ZeroEntropy Python SDK](https://github.com/zeroentropy-ai/zeroentropy-python) to read every document from a ZeroEntropy collection and copy it into a Moss index, so you can migrate off ZeroEntropy in a few lines.

## Install

```bash
pip install moss-connector-zeroentropy
```

This installs `zeroentropy` automatically.

## Usage

Migrating a whole collection needs no mapper: the default mapping uses each document's `path` as the Moss id, its parsed `content` as the searchable text, and copies its metadata.

```python
import asyncio
from moss_connector_zeroentropy import ZeroEntropyConnector, ingest

async def main():
    source = ZeroEntropyConnector(
        collection_name="my_collection",
        api_key="your-zeroentropy-key",  # or set ZEROENTROPY_API_KEY
    )

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="my_collection",
    )
    print(f"migrated {result.doc_count} documents")

asyncio.run(main())
```

Set `ZEROENTROPY_API_KEY` in the environment and drop `api_key=` entirely.

### Custom mapping

Pass a `mapper` to control the `DocumentInfo`. It receives one row dict per document, holding the document's ZeroEntropy fields (`id`, `path`, `metadata`, `file_url`, `index_status`, `num_pages`, `size`) plus the fetched `content`:

```python
source = ZeroEntropyConnector(
    collection_name="my_collection",
    mapper=lambda row: DocumentInfo(
        id=row["id"],                     # ZeroEntropy's UUID instead of the path
        text=row["content"],
        metadata={"path": row["path"], "pages": str(row["num_pages"])},
    ),
)
```

Use `auto_id=True` on `ingest(...)` to have Moss generate UUID document ids instead.

## Migrating every collection

The SDK can list your collections, so migrating all of them is a loop:

```python
from zeroentropy import ZeroEntropy

ze = ZeroEntropy(api_key="your-zeroentropy-key")
for name in ze.collections.get_list().collection_names:
    source = ZeroEntropyConnector(collection_name=name, api_key="your-zeroentropy-key")
    await ingest(source, project_id="...", project_key="...", index_name=name)
```

## Data requirements

The connector doesn't impose a schema — it hands each document to your `mapper` as a dict. The constraints come from `DocumentInfo`, not the connector.

`DocumentInfo` fields:

| Field | Type | Required? | Source in a ZeroEntropy document |
|---|---|---|---|
| `id` | `str` | yes | `path` (default) or `id` |
| `text` | `str` | yes | `content` (the parsed document text) |
| `metadata` | `Optional[Dict[str, str]]` | no | `metadata` |
| `embedding` | `Optional[Sequence[float]]` | no | not exported by ZeroEntropy |

### Metadata values must be strings

ZeroEntropy metadata is typed `Dict[str, str | list[str]]` — a value can be a single string **or a list of strings**. `DocumentInfo.metadata` requires `Dict[str, str]`, so the default mapper coerces list values by joining them with `", "` (via `coerce_metadata`). If you write your own mapper, coerce list-valued metadata yourself:

```python
# WILL FAIL — a list value
metadata={"tags": row["metadata"]["tags"]}

# CORRECT
metadata={"tags": ", ".join(row["metadata"]["tags"])}
```

## Content and skipped documents

The list endpoint (`documents.get_info_list`) returns metadata only, so the connector fetches each document's text with `documents.get_info(..., include_content=True)` — one call per document. A document that never parsed (`index_status` of `parsing_failed`, `parsing`, etc.) has no `content`; the connector **skips it** rather than indexing an empty document into Moss.

To migrate metadata only (no per-document content fetch), pass `include_content=False` and a `mapper` that does not read `content`.

To restrict the migration to a subtree, pass `path_prefix="docs/2024/"`.

## Pagination

`documents.get_info_list` is an auto-paginating cursor, so the connector iterates every page transparently — there is no page-size knob to tune.

## Layout

```
src/
├── __init__.py      # re-exports ZeroEntropyConnector, ingest, default_mapper, coerce_metadata
├── connector.py     # ZeroEntropyConnector + default_mapper + coerce_metadata
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_zeroentropy.py -v                            # mocked, no network needed
pytest tests/test_integration_zeroentropy_moss.py -v -s        # live ZeroEntropy + Moss
```

The integration test requires `ZEROENTROPY_API_KEY`, `ZEROENTROPY_TEST_COLLECTION` (a pre-populated collection), `MOSS_PROJECT_ID`, and `MOSS_PROJECT_KEY`.
