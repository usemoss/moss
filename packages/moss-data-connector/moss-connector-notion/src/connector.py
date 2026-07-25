"""Notion Connector for Moss."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from moss import DocumentInfo
from notion_client import Client


class NotionConnector:
    """Read from Notion and yield DocumentInfo objects."""

    def __init__(
        self,
        token: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        query: str | None = None,
        filter_fn: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.token = token
        self.query = query
        self.mapper = mapper
        self.filter_fn = filter_fn

    def _fetch_blocks(
        self,
        client: Client,
        block_id: str,
    ) -> list[dict[str, Any]]:
        all_blocks: list[dict[str, Any]] = []

        cursor = None

        while True:
            kwargs: dict[str, Any] = {"block_id": block_id}
            if cursor is not None:
                kwargs["start_cursor"] = cursor
            response = client.blocks.children.list(**kwargs)

            blocks = response["results"] or []

            for block in blocks:
                if block.get("has_children"):
                    block = {
                        **block,
                        "children": self._fetch_blocks(
                            client,
                            block["id"],
                        ),
                    }

                all_blocks.append(block)

            if not response["has_more"]:
                break

            cursor = response["next_cursor"]

        return all_blocks

    def __iter__(self) -> Iterator[DocumentInfo]:
        FILTER = {
            "property": "object",
            "value": "page",
        }

        client = Client(auth=self.token)

        page_cursor = None

        while True:
            kwargs: dict[str, Any] = {
                "filter": FILTER,
            }

            if self.query is not None:
                kwargs["query"] = self.query

            if page_cursor is not None:
                kwargs["start_cursor"] = page_cursor

            search_response = client.search(**kwargs)

            pages = search_response["results"] or []

            if not pages:
                break

            for page in pages:
                page = {
                    **page,
                    "content": self._fetch_blocks(
                        client,
                        page["id"],
                    ),
                }

                if self.filter_fn is not None and not self.filter_fn(page):
                    continue

                yield self.mapper(page)

            if not search_response["has_more"]:
                break

            page_cursor = search_response["next_cursor"]
