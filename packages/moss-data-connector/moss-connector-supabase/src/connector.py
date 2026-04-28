from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from moss import DocumentInfo
from supabase import create_client


class SupabaseConnector:
    def __init__(
        self,
        url: str,
        key: str,
        table: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        select: str = "*",
        page_size: int = 1000,
    ) -> None:
        self.url = url
        self.key = key
        self.table = table
        self.mapper = mapper
        self.select = select
        self.page_size = page_size

    def __iter__(self) -> Iterator[DocumentInfo]:
        client = create_client(self.url, self.key)
        start = 0
        while True:
            end = start + self.page_size - 1
            resp = client.table(self.table).select(self.select).range(start, end).execute()
            rows = resp.data or []
            if not rows:
                return
            for row in rows:
                yield self.mapper(row)
            if len(rows) < self.page_size:
                return
            start += self.page_size
