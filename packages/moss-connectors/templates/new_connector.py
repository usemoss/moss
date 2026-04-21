"""Template for a new connector. Copy into
`src/moss_connectors/connectors/<source>.py` and fill in the TODOs.

A connector is anything you can iterate over that yields one dict per row.
Classes with `__iter__` are the convention (good IDE discoverability), but a
generator function works too.
"""

from __future__ import annotations

from typing import Any, Iterator


class MySourceConnector:
    def __init__(self, connection_string: str, query: str) -> None:
        # TODO: store whatever config your source needs.
        self.connection_string = connection_string
        self.query = query

    def __iter__(self) -> Iterator[dict[str, Any]]:
        # TODO: connect, run the query, yield one dict per row.
        # The dict must contain the id column named in DocumentMapping.id.
        raise NotImplementedError
