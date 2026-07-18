# moss-connector-s3

Amazon S3 source connector for Moss. Reads objects from an S3 bucket and
ingests them into a Moss index via `boto3`, with an optional `watch()` loop
that re-indexes whenever the bucket contents change.

## Install

```bash
pip install moss-connector-s3
```

Pulls `boto3` as a dependency. AWS credentials must be configured separately
(environment variables, `~/.aws/credentials`, or an IAM role).

## Usage — one-shot ingest

```python
import asyncio
from moss import DocumentInfo
from moss_connector_s3 import S3Connector, ingest

async def main():
    source = S3Connector(
        bucket="my-content-bucket",
        prefix="kb/",          # only keys under kb/
        suffix=".md",          # only markdown objects
        mapper=lambda row: DocumentInfo(
            id=row["key"],
            text=row["text"],
            metadata={"category": row["metadata"].get("category", "")},
        ),
        region_name="us-east-1",
    )

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="knowledge-base",
    )
    if result is None:
        print("no matching objects found")
    else:
        print(f"copied {result.doc_count} objects")

asyncio.run(main())
```

`ingest()` returns `None` when the bucket is empty or no objects match your
filters. Pass `auto_id=True` to `ingest()` when your object keys are not
stable ids and you want Moss to generate UUID document IDs.

## Usage — watch a bucket (re-index on change)

`watch()` ingests the bucket once, then polls it and rebuilds the index
whenever an object is added, removed, or modified (detected by comparing
`{key: etag}` snapshots — polls only *list* the bucket; bodies are downloaded
only when a re-index actually runs):

```python
import asyncio
from moss import DocumentInfo
from moss_connector_s3 import S3Connector, watch

async def main():
    source = S3Connector(
        bucket="my-content-bucket",
        prefix="kb/",
        mapper=lambda row: DocumentInfo(id=row["key"], text=row["text"]),
        region_name="us-east-1",
    )
    # Runs until cancelled; re-creates the index on every bucket change.
    await watch(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="knowledge-base",
        poll_interval=60.0,   # seconds between bucket snapshots
    )

asyncio.run(main())
```

Pass `max_polls=N` to stop after N polls (useful for one-shot sync jobs in a
scheduler), and `on_change=callback` (sync or async) to be notified with the
new `{key: etag}` snapshot after each re-index.

If every matching object is deleted from the bucket, `watch()` deletes the
Moss index rather than leaving stale documents searchable; the index is
re-created on the next change that adds objects back.

## What the mapper receives

Each object becomes a `dict` row with these keys:

| Key             | Value                                                |
| --------------- | ---------------------------------------------------- |
| `key`           | the object key                                       |
| `text`          | object body decoded with `encoding` (default UTF-8)  |
| `etag`          | the object's ETag, surrounding quotes stripped       |
| `last_modified` | `datetime` of last modification                      |
| `size`          | object size in bytes                                 |
| `content_type`  | the object's Content-Type, if any                    |
| `metadata`      | the object's S3 user metadata (`x-amz-meta-*`)       |

`DocumentInfo.metadata` requires `Dict[str, str]` — coerce non-string values
in your mapper:

```python
mapper=lambda row: DocumentInfo(
    id=row["key"],
    text=row["text"],
    metadata={
        "size": str(row["size"]),
        "modified": row["last_modified"].isoformat(),
    },
)
```

## Filtering

- `prefix="kb/"` restricts listing server-side (cheap — S3 filters before
  returning keys).
- `suffix=".md"` (or a tuple like `(".md", ".txt")`) filters client-side;
  non-matching objects are skipped without being downloaded.
- Keys ending in `/` (zero-byte "folder" placeholders created by the S3
  console) are always skipped.

## Pagination

Objects are listed with `list_objects_v2` and paged automatically via
continuation tokens, so you get every object regardless of bucket size. Tune
`page_size` (default `1000`, the S3 maximum) to control keys per round-trip.

## Connecting to MinIO / LocalStack

Pass `endpoint_url` to the connector:

```python
S3Connector(
    bucket="my-bucket",
    mapper=...,
    region_name="us-east-1",
    endpoint_url="http://localhost:9000",   # MinIO
)
```

## Layout

```
src/
├── __init__.py      # re-exports S3Connector, ingest, watch
├── connector.py     # S3Connector class (list, fetch, snapshot)
├── watch.py         # watch() — poll the bucket, re-index on change
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_s3.py -v                       # mocked with moto, no AWS needed
pytest tests/test_integration_s3_moss.py -v -s   # live S3 (or MinIO/LocalStack) + Moss
```

The mocked tests use [moto](https://github.com/getmoto/moto) to simulate S3
locally — no AWS credentials needed.

The integration test requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`MOSS_PROJECT_ID`, and `MOSS_PROJECT_KEY`. Set `S3_ENDPOINT_URL=http://localhost:9000`
to target MinIO (or `http://localhost:4566` for LocalStack) instead of real AWS.
