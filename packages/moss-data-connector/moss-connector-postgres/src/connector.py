"""PostgreSQL connector.

Reads rows from a PostgreSQL database via ``psycopg`` (v3) and yields one
``DocumentInfo`` per row. Uses ``DictRow`` factory so every row is a plain dict
keyed by column name.

Works against regular Postgres, Neon, Supabase (direct URL), CockroachDB,
Amazon RDS, Timescale, and pgvector.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import psycopg.rows
from moss import DocumentInfo


class PostgresConnector:
    """Run a SELECT against a PostgreSQL database and yield one
    ``DocumentInfo`` per row.

    ``mapper`` turns a row (dict of column → value) into a ``DocumentInfo``;
    the caller decides which columns become id / text / metadata / embedding.
    """

    def __init__(
        self,
        dsn: str,
        query: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
    ) -> None:
        self.dsn = dsn
        self.query = query
        self.mapper = mapper

    def __iter__(self) -> Iterator[DocumentInfo]:
        conn = psycopg.connect(self.dsn, row_factory=psycopg.rows.dict_row)
        try:
            with conn.cursor() as cursor:
                cursor.execute(self.query)
                for row in cursor:
                    yield self.mapper(row)
        finally:
            conn.close()
