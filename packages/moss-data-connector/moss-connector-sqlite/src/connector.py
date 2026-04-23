"""SQLite connector - the reference implementation.

Uses only the stdlib so it doubles as a zero-dep test fixture.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Iterator

from moss import DocumentInfo


class SQLiteConnector:
    """Run a SELECT against a SQLite database and yield one `DocumentInfo` per row.

    `mapper` turns a row (dict of column -> value) into a `DocumentInfo`, the
    caller decides which columns become id / text / metadata / embedding.
    """

    def __init__(
        self,
        database: str,
        query: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
    ) -> None:
        self.database = database
        self.query = query
        self.mapper = mapper

    def __iter__(self) -> Iterator[DocumentInfo]:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(self.query):
                yield self.mapper(dict(row))
        finally:
            conn.close()
