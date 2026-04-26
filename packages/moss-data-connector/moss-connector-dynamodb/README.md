# moss-connector-dynamodb

DynamoDB source connector for Moss. Scans an entire table (with optional filters) and ingests items into a Moss search index.

## Install

```bash
pip install moss-connector-dynamodb
```

Pulls `boto3` as a dependency. Uses the standard boto3 credential chain (env vars, shared credentials file, IAM role, etc.).

## Usage

```python
import asyncio
from moss import DocumentInfo
from moss_connector_dynamodb import DynamoDBConnector, ingest

async def main():
    source = DynamoDBConnector(
        table_name="articles",
        mapper=lambda item: DocumentInfo(
            id=str(item["id"]),
            text=item["body"],
            metadata={"title": item["title"]},
        ),
        region_name="us-east-1",
        scan_kwargs={                                          # optional
            "FilterExpression": "#s = :val",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {":val": "published"},
        },
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

DynamoDB items come back as dicts with Python types (Decimal for numbers, etc.). Handle type coercion in your mapper.

For large tables, `ingest()` loads all items into memory before indexing. Consider batching for tables with 100K+ rows.

### Local development

Pass `endpoint_url` to target DynamoDB Local or localstack:

```python
source = DynamoDBConnector(
    table_name="articles",
    mapper=my_mapper,
    endpoint_url="http://localhost:8000",
)
```

## Layout

```
src/
├── __init__.py      # re-exports DynamoDBConnector and ingest
├── connector.py     # DynamoDBConnector class
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_dynamodb.py -v                              # mocked Moss + mocked boto3
pytest tests/test_integration_dynamodb_moss.py -v -s          # live Moss + real DynamoDB
```

The live integration test requires `DYNAMODB_TABLE`, `AWS_REGION`, `MOSS_PROJECT_ID`, and `MOSS_PROJECT_KEY` env vars. Optionally set `DYNAMODB_ENDPOINT_URL` for DynamoDB Local.
