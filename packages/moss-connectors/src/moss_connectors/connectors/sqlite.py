"""SQLite connector — the reference implementation.

Uses only the stdlib so it doubles as a zero-dep test fixture.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterator


class SQLiteConnector:
    """Run a SELECT against a SQLite database and yield one dict per row."""

    def __init__(self, database: str, query: str) -> None:
        self.database = database
        self.query = query

    def __iter__(self) -> Iterator[dict[str, Any]]:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        try:
            for row in conn.execute(self.query):
                yield dict(row)
        finally:
            conn.close()
