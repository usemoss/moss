"""Integration test for moss-connector-notion."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytest.importorskip("notion_client")

from moss import DocumentInfo, MossClient, QueryOptions
from moss_connector_notion import NotionConnector, ingest
from notion_client import Client

try:
    from dotenv import load_dotenv

    _here = Path(__file__).resolve()
    for candidate in (
        _here.parents[1] / ".env",
        _here.parents[2] / ".env",
        _here.parents[4] / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)
except ImportError:
    pass

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_PARENT_PAGE_ID = os.getenv("NOTION_PARENT_PAGE_ID")
MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")

pytestmark = pytest.mark.skipif(
    not (NOTION_TOKEN and NOTION_PARENT_PAGE_ID and MOSS_PROJECT_ID and MOSS_PROJECT_KEY),
    reason=("Set NOTION_TOKEN, NOTION_PARENT_PAGE_ID, MOSS_PROJECT_ID and MOSS_PROJECT_KEY."),
)


def flatten_blocks(blocks: list[dict]) -> str:
    """Convert a Notion block tree into plain text."""

    lines: list[str] = []

    def visit(block: dict):
        block_type = block.get("type")

        if block_type:
            payload = block.get(block_type, {})
            rich_text = payload.get("rich_text", [])

            if rich_text:
                text = "".join(part.get("plain_text", "") for part in rich_text)

                if text:
                    lines.append(text)

        for child in block.get("children", []):
            visit(child)

    for block in blocks:
        visit(block)

    return "\n".join(lines)


async def test_notion_ingest_end_to_end():
    notion = Client(auth=NOTION_TOKEN)
    moss = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)

    unique = uuid.uuid4().hex[:8]
    title = f"Moss Integration Test {unique}"

    page = notion.pages.create(
        parent={
            "type": "page_id",
            "page_id": NOTION_PARENT_PAGE_ID,
        },
        properties={
            "title": {
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": title,
                        },
                    }
                ]
            }
        },
    )

    page_id = page["id"]

    notion.blocks.children.append(
        block_id=page_id,
        children=[
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Rust Learning Roadmap",
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    "Study ownership, borrowing and lifetimes "
                                    "before learning async Rust."
                                ),
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Competitive Programming",
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    "Practice Fenwick Tree, Segment Tree and "
                                    "Binary Lifting problems every weekend."
                                ),
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "Backend Project",
                            },
                        }
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": (
                                    "Build a low-latency websocket server using Rust and Tokio."
                                ),
                            },
                        }
                    ]
                },
            },
        ],
    )

    index_name = f"moss-notion-e2e-{uuid.uuid4().hex[:8]}"

    try:
        connector = NotionConnector(
            token=NOTION_TOKEN,
            query=title,
            mapper=lambda page: DocumentInfo(
                id=page["id"],
                text=flatten_blocks(page["content"]),
                metadata={
                    "url": page["url"],
                },
            ),
        )

        result = await ingest(
            connector,
            MOSS_PROJECT_ID,
            MOSS_PROJECT_KEY,
            index_name=index_name,
        )

        assert result is not None
        assert result.doc_count == 1

        await moss.load_index(index_name)

        result = await moss.query(
            index_name,
            "What concepts should I study before learning async Rust?",
            QueryOptions(top_k=3),
        )

        assert result.docs, "Expected at least one search result."

        top = result.docs[0].text.lower()

        assert "ownership" in top
        assert "borrowing" in top
        assert "lifetimes" in top

    finally:
        try:
            await moss.delete_index(index_name)
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to delete test index {index_name}: {exc}")

        try:
            notion.pages.update(
                page_id=page_id,
                archived=True,
            )
        except Exception as exc:  # pragma: no cover
            print(f"warning: failed to archive test page {page_id}: {exc}")
