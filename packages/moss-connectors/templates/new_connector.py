"""Template for a new connector. Copy into
`src/moss_connectors/connectors/<source>.py` and fill in the TODOs.

A connector is anything you can iterate over that yields one `DocumentInfo`
per row. Accept a `mapper` callable in `__init__` so the caller controls how
source rows become documents — don't hardcode the mapping.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

from moss import DocumentInfo


class MySourceConnector:
    def __init__(
        self,
        connection_string: str,
        query: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
    ) -> None:
        # TODO: store whatever config your source needs.
        self.connection_string = connection_string
        self.query = query
        self.mapper = mapper

    def __iter__(self) -> Iterator[DocumentInfo]:
        # TODO: connect, run the query, and for each row:
        #   yield self.mapper(row_as_dict)
        # Don't pre-filter columns — the caller's mapper decides what to use.
        raise NotImplementedError
