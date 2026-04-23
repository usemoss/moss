"""Connector class goes here. Rename both the file's class and the module's
host package (`moss_connector_template` → `moss_connector_<source>`).
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

from moss import DocumentInfo


class TemplateConnector:
    """Yield one `DocumentInfo` per row from your source.

    `mapper` turns one row dict into a `DocumentInfo`, the caller decides
    which keys become id / text / metadata / embedding.
    """

    def __init__(
        self,
        # TODO: add your source-specific config here (connection string, query, etc.)
        mapper: Callable[[dict[str, Any]], DocumentInfo],
    ) -> None:
        self.mapper = mapper

    def __iter__(self) -> Iterator[DocumentInfo]:
        # TODO: connect to your source, pull rows, and for each one:
        #   yield self.mapper(row_as_dict)
        # Don't pre-filter columns - the caller's mapper decides what to use.
        # Import your driver *inside* this method, not at module top, so
        # importing the package never fails just because the driver isn't
        # installed.
        raise NotImplementedError
