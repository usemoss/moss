# moss-connector-notion

Notion source connector for Moss. Uses the official [notion-client](https://github.com/ramnes/notion-sdk-py) to read pages from a Notion workspace and ingest them into a Moss index.

## Install

```bash
pip install moss-connector-notion
```

This installs `notion-client` automatically.

## Usage

```python
import asyncio

from moss import DocumentInfo
from moss_connector_notion import NotionConnector, ingest


def flatten_blocks(blocks: list[dict]) -> str:
    lines = []

    def visit(block):
        block_type = block.get("type")

        if block_type:
            payload = block.get(block_type, {})
            rich_text = payload.get("rich_text", [])

            if rich_text:
                lines.append(
                    "".join(part.get("plain_text", "") for part in rich_text)
                )

        for child in block.get("children", []):
            visit(child)

    for block in blocks:
        visit(block)

    return "\n".join(lines)


async def main():
    source = NotionConnector(
        token="your_notion_token",
        query="Rust",
        mapper=lambda page: DocumentInfo(
            id=page["id"],
            text=flatten_blocks(page["content"]),
            metadata={
                "url": page["url"],
            },
        ),
    )

    result = await ingest(
        source,
        project_id="your_project_id",
        project_key="your_project_key",
        index_name="notion-pages",
    )

    print(f"Copied {result.doc_count} pages")


asyncio.run(main())
```

Use `auto_id=True` when your mapper does not have a stable document ID and you want Moss to generate UUID document IDs.

## Data requirements

The connector doesn't enforce a schema. Every Notion page is returned as a Python dictionary with one additional field:

```python
page["content"]
```

`content` contains the complete block tree for the page, including nested child blocks.

The connector passes this page dictionary directly to your mapper. The mapper is responsible for converting it into a `DocumentInfo`.

`DocumentInfo` fields:

| Field | Type | Required? | Typical Notion value |
| --- | --- | --- | --- |
| `id` | `str` | yes | `page["id"]` |
| `text` | `str` | yes | extracted text from `page["content"]` |
| `metadata` | `Optional[Dict[str, str]]` | no | page URL, title, author, etc. |
| `embedding` | `Optional[Sequence[float]]` | no | only when using `model_id="custom"` |

A typical mapper looks like:

```python
mapper=lambda page: DocumentInfo(
    id=page["id"],
    text=flatten_blocks(page["content"]),
    metadata={
        "url": page["url"],
    },
)
```

## One gotcha: metadata values must be strings

`DocumentInfo.metadata` expects `Dict[str, str]`.

If you include values that are numbers, booleans or lists, convert them first.

```python
# Incorrect
metadata={
    "views": 42,
    "published": True,
}

# Correct
metadata={
    "views": str(42),
    "published": str(True),
}
```

## Authentication

Create a Notion integration and copy its internal integration token.

The integration only has access to pages that have been explicitly shared with it.

If a page doesn't appear during ingestion:

1. Open the page in Notion.
2. Click **Share**.
3. Invite your integration.

## Searching pages

The connector optionally accepts a `query` argument.

```python
NotionConnector(
    token=TOKEN,
    query="Python",
    ...
)
```

This uses Notion's built-in search API and only returns matching pages.

If `query` is omitted, every page visible to the integration is scanned.

## Filtering

The connector supports client-side filtering through `filter_fn`.

```python
source = NotionConnector(
    token=TOKEN,
    filter_fn=lambda page: page["url"].startswith("https://"),
    mapper=...,
)
```

The filter runs after the page and all of its blocks have been fetched.

It receives the complete page dictionary, including the `content` field.

## Nested blocks

Notion pages can contain nested blocks (toggles, lists, callouts, etc.).

The connector recursively fetches all child blocks before yielding the page, so `page["content"]` always contains the complete block tree.

The connector does **not** flatten or modify the content. This is left to the mapper so applications can decide how much structure to preserve.

## Pagination

The connector handles pagination automatically.

Both page search results and block children are fetched across multiple requests until all results have been retrieved.

No additional configuration is required.

## Layout

```
src/
├── __init__.py      # re-exports NotionConnector and ingest
├── connector.py     # NotionConnector class
└── ingest.py        # ingest() - shared across connector packages
```

## Tests

```bash
pip install -e ".[dev]"

pytest tests/test_notion.py -v
pytest tests/test_notion_integration.py -v -s
```

The integration test requires:

- `NOTION_TOKEN`
- `NOTION_PARENT_PAGE_ID`
- `MOSS_PROJECT_ID`
- `MOSS_PROJECT_KEY`

The test creates a temporary child page under `NOTION_PARENT_PAGE_ID`, ingests it into Moss, verifies semantic search, and archives the page after the test completes.