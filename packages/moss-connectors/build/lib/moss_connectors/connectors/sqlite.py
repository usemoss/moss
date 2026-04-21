"""SQLite connector — the reference implementation.

Uses only the stdlib so it doubles as a zero-dep test fixture.
"""

from __future__ import annotations

import sqlite3
from typing import Iterator

from ..base import Connector, Record


class SQLiteConnector(Connector):
    """Run a SELECT against a SQLite database and yield one Record per row.

    The `id_column` must be present in the query's projection.
    """

    def __init__(self, database: str, query: str, id_column: str = "id") -> None:
        self.database = database
        self.query = query
        self.id_column = id_column

    def read(self) -> Iterator[Record]:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(self.query):
                fields = dict(row)
                yield Record(id=str(fields[self.id_column]), fields=fields)
        finally:
            conn.close()
