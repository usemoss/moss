"""Unit tests for moss-connector-notion."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("notion_client")

from moss import DocumentInfo
from moss_connector_notion import NotionConnector, ingest


@dataclass
class FakeMutationResult:
    doc_count: int
    job_id: str = "fake-job-id"
    index_name: str = ""


@dataclass
class FakeMossClient:
    """Records create_index calls without hitting the network."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_index(self, name, docs, model_id=None):
        self.calls.append({"name": name, "docs": list(docs), "model_id": model_id})
        return FakeMutationResult(doc_count=len(docs), index_name=name)


async def test_notion_ingest_end_to_end():
    fake_client = MagicMock()

    fake_client.search.return_value = {
        "results": [
            {
                "id": "page1",
                "url": "https://notion.so/page1",
            },
            {
                "id": "page2",
                "url": "https://notion.so/page2",
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }

    fake_client.blocks.children.list.side_effect = [
        {
            "results": [
                {
                    "id": "block1",
                    "type": "paragraph",
                    "has_children": False,
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
        {
            "results": [
                {
                    "id": "block2",
                    "type": "paragraph",
                    "has_children": False,
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    fake_moss = FakeMossClient()

    with (
        patch(
            "moss_connector_notion.connector.Client",
            return_value=fake_client,
        ),
        patch(
            "moss_connector_notion.ingest.MossClient",
            return_value=fake_moss,
        ),
    ):
        source = NotionConnector(
            token="fake-token",
            mapper=lambda page: DocumentInfo(
                id=page["id"],
                text=str(page["content"]),
                metadata={
                    "url": page["url"],
                },
            ),
        )

        result = await ingest(
            source,
            "fake_project",
            "fake_key",
            "notion",
        )

    assert result is not None
    assert result.doc_count == 2

    assert len(fake_moss.calls) == 1

    docs = fake_moss.calls[0]["docs"]

    assert docs[0].id == "page1"
    assert docs[1].id == "page2"

    assert docs[0].metadata == {
        "url": "https://notion.so/page1",
    }

    assert docs[1].metadata == {
        "url": "https://notion.so/page2",
    }

    assert docs[0].text
    assert docs[1].text

    assert fake_client.search.call_count == 1
    assert fake_client.blocks.children.list.call_count == 2


async def test_search_pagination():
    fake_client = MagicMock()

    fake_client.search.side_effect = [
        {
            "results": [
                {
                    "id": "page1",
                    "url": "u1",
                }
            ],
            "has_more": True,
            "next_cursor": "cursor1",
        },
        {
            "results": [
                {
                    "id": "page2",
                    "url": "u2",
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    fake_client.blocks.children.list.side_effect = [
        {
            "results": [],
            "has_more": False,
            "next_cursor": None,
        },
        {
            "results": [],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    fake_moss = FakeMossClient()

    with (
        patch(
            "moss_connector_notion.connector.Client",
            return_value=fake_client,
        ),
        patch(
            "moss_connector_notion.ingest.MossClient",
            return_value=fake_moss,
        ),
    ):
        source = NotionConnector(
            token="fake-token",
            mapper=lambda page: DocumentInfo(
                id=page["id"],
                text="",
            ),
        )

        result = await ingest(
            source,
            "fake_project",
            "fake_key",
            "notion",
        )

    assert result is not None
    assert result.doc_count == 2

    docs = fake_moss.calls[0]["docs"]

    assert [doc.id for doc in docs] == [
        "page1",
        "page2",
    ]

    assert fake_client.search.call_count == 2

    first_call = fake_client.search.call_args_list[0]
    second_call = fake_client.search.call_args_list[1]

    assert "start_cursor" not in first_call.kwargs
    assert second_call.kwargs["start_cursor"] == "cursor1"


async def test_block_pagination():
    fake_client = MagicMock()

    fake_client.search.return_value = {
        "results": [
            {
                "id": "page1",
                "url": "u1",
            }
        ],
        "has_more": False,
        "next_cursor": None,
    }

    fake_client.blocks.children.list.side_effect = [
        {
            "results": [
                {
                    "id": "block1",
                    "type": "paragraph",
                    "has_children": False,
                },
                {
                    "id": "block2",
                    "type": "paragraph",
                    "has_children": False,
                },
            ],
            "has_more": True,
            "next_cursor": "cursor1",
        },
        {
            "results": [
                {
                    "id": "block3",
                    "type": "paragraph",
                    "has_children": False,
                },
            ],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    source = NotionConnector(
        token="fake-token",
        mapper=lambda page: DocumentInfo(
            id=page["id"],
            text=" ".join(block["id"] for block in page["content"]),
            metadata={
                "page_id": page["id"],
            },
        ),
    )

    with patch(
        "moss_connector_notion.connector.Client",
        return_value=fake_client,
    ):
        docs = list(source)

    assert len(docs) == 1
    assert docs[0].id == "page1"
    assert docs[0].text == "block1 block2 block3"

    assert fake_client.blocks.children.list.call_count == 2

    first = fake_client.blocks.children.list.call_args_list[0]
    second = fake_client.blocks.children.list.call_args_list[1]

    assert first.kwargs["block_id"] == "page1"
    assert "start_cursor" not in first.kwargs
    assert second.kwargs["start_cursor"] == "cursor1"


async def test_recursive_block_fetch():
    fake_client = MagicMock()

    fake_client.search.return_value = {
        "results": [
            {
                "id": "page1",
                "url": "u1",
            }
        ],
        "has_more": False,
        "next_cursor": None,
    }

    fake_client.blocks.children.list.side_effect = [
        {
            "results": [
                {
                    "id": "toggle1",
                    "type": "toggle",
                    "has_children": True,
                }
            ],
            "has_more": False,
            "next_cursor": None,
        },
        {
            "results": [
                {
                    "id": "paragraph1",
                    "type": "paragraph",
                    "has_children": False,
                },
                {
                    "id": "code1",
                    "type": "code",
                    "has_children": False,
                },
            ],
            "has_more": False,
            "next_cursor": None,
        },
    ]

    def flatten(blocks):
        out = []

        def dfs(block):
            out.append(block["id"])
            for child in block.get("children", []):
                dfs(child)

        for block in blocks:
            dfs(block)

        return " ".join(out)

    source = NotionConnector(
        token="fake-token",
        mapper=lambda page: DocumentInfo(
            id=page["id"],
            text=flatten(page["content"]),
            metadata={
                "page_id": page["id"],
            },
        ),
    )

    with patch(
        "moss_connector_notion.connector.Client",
        return_value=fake_client,
    ):
        docs = list(source)

    assert len(docs) == 1
    assert docs[0].id == "page1"
    assert docs[0].text == "toggle1 paragraph1 code1"

    assert fake_client.blocks.children.list.call_count == 2
