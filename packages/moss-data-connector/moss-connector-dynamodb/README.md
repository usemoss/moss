# moss-connector-dynamodb

Amazon DynamoDB source connector for Moss. Reads items from a DynamoDB table
and ingests them into a Moss index via `boto3`.

## Install

```bash
pip install moss-connector-dynamodb
```

Pulls `boto3` as a dependency. AWS credentials must be configured separately
(environment variables, `~/.aws/credentials`, or an IAM role).

## Usage — full-table Scan

```python
import asyncio
from moss import DocumentInfo
from moss_connector_dynamodb import DynamoDBConnector, ingest

async def main():
    source = DynamoDBConnector(
        table_name="articles",
        mapper=lambda item: DocumentInfo(
            id=item["sku"],
            text=item["body"],
            metadata={"title": item["title"]},
        ),
        region_name="us-east-1",
    )

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="articles",
    )
    print(f"copied {result.doc_count} items")

asyncio.run(main())
```

Use `auto_id=True` when your mapper does not have a stable primary key and you
want Moss to generate UUID document IDs.

## Usage — partition-key Query

Use `DynamoDBQueryConnector` when you only want items for a specific partition:

```python
from boto3.dynamodb.conditions import Key
from moss import DocumentInfo
from moss_connector_dynamodb import DynamoDBQueryConnector, ingest

source = DynamoDBQueryConnector(
    table_name="events",
    key_condition_expression=Key("tenant_id").eq("acme"),
    mapper=lambda item: DocumentInfo(
        id=item["event_id"],
        text=item["description"],
        metadata={"tenant_id": item["tenant_id"]},
    ),
    region_name="us-east-1",
)
```

## Filtering (Scan)

Pass a boto3 `FilterExpression` to restrict which items the connector yields:

```python
from boto3.dynamodb.conditions import Attr

source = DynamoDBConnector(
    table_name="articles",
    filter_expression=Attr("status").eq("published"),
    mapper=...,
    region_name="us-east-1",
)
```

`FilterExpression` is applied server-side by DynamoDB *after* the Scan reads
items — it does not reduce consumed capacity, but it does reduce the data
your Lambda / server has to process. For true server-side filtering, use
a Query with `DynamoDBQueryConnector` or a DynamoDB Stream / Filter Policy.

## Pagination

Both connectors automatically follow `LastEvaluatedKey` pagination so you get
every item in the table regardless of size. Tune `page_size` (default `100`)
to control how many items are fetched per round-trip.

## Data requirements

`DocumentInfo.metadata` requires `Dict[str, str]`. DynamoDB's high-level
resource API returns `Decimal` for numbers and `bytes` for Binary. Coerce
non-string values in your mapper:

```python
mapper=lambda item: DocumentInfo(
    id=item["id"],
    text=item["content"],
    metadata={
        "price": str(item["price"]),        # Decimal → str
        "in_stock": str(item["in_stock"]),  # bool → str
        "tags": ",".join(item["tags"]),     # set/list → str
    },
)
```

## Connecting to DynamoDB Local / LocalStack

Pass `endpoint_url` to the connector:

```python
DynamoDBConnector(
    table_name="articles",
    mapper=...,
    region_name="us-east-1",
    endpoint_url="http://localhost:8000",   # DynamoDB Local
)
```

## Layout

```
src/
├── __init__.py      # re-exports DynamoDBConnector, DynamoDBQueryConnector, ingest
├── connector.py     # DynamoDBConnector and DynamoDBQueryConnector classes
└── ingest.py        # ingest() - keep in sync with the other connector packages
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_dynamodb.py -v                          # mocked with moto, no AWS needed
pytest tests/test_integration_dynamodb_moss.py -v -s      # live AWS + Moss
```

The mocked tests use [moto](https://github.com/getmoto/moto) to simulate DynamoDB locally — no AWS credentials needed.

The integration test requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`MOSS_PROJECT_ID`, and `MOSS_PROJECT_KEY`. Set `DYNAMODB_ENDPOINT_URL=http://localhost:8000`
to target a local DynamoDB instead of real AWS.
