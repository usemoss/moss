# moss-connector-mongodb

MongoDB source connector for Moss. Self-contained, no separate core package to install.

## Install

```bash
pip install moss-connector-mongodb
```

Pulls `pymongo` as a dependency.

## Usage

```python
import asyncio
from moss import DocumentInfo
from moss_connector_mongodb import MongoDBConnector, ingest

async def main():
    source = MongoDBConnector(
        uri="mongodb://localhost:27017",
        database="shop",
        collection="articles",
        mapper=lambda r: DocumentInfo(
            id=str(r["_id"]),
            text=r["body"],
            metadata={"title": r["title"]},
        ),
        filter={"status": "published"},                # optional
        projection={"_id": 1, "title": 1, "body": 1},  # optional
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

MongoDB's `_id` is a `bson.ObjectId`. Wrap it with `str()` in your mapper to render the hex string.

## Layout

```
src/
├── __init__.py      # re-exports MongoDBConnector and ingest
├── connector.py     # MongoDBConnector class
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_mongodb.py -v                       # mocked Moss + mocked Mongo
pytest tests/test_integration_mongodb_moss.py -v -s   # live Moss + local Mongo
```

The live integration test expects a Mongo at `mongodb://localhost:27017` - edit `MONGODB_URI` at the top of the test file to change.
