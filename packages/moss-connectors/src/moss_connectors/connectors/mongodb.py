"""MongoDB connector.

Reads documents from a MongoDB collection via pymongo's `find()`. One yielded
dict per document.

Install with:
    pip install "moss-connectors[mongodb]"

Note on ids: MongoDB's `_id` comes back as a `bson.ObjectId`. Map it with
`DocumentMapping(id="_id", ...)` — `ingest()` calls `str()` on the id, which
renders ObjectIds as their hex string.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional


class MongoDBConnector:
    """Read documents from a MongoDB collection and yield one dict per document.

    By default yields every document in the collection. Pass `filter` to
    restrict results (any standard Mongo query dict). Pass `projection` to
    limit which fields come back.
    """

    def __init__(
        self,
        uri: str,
        database: str,
        collection: str,
        filter: Optional[dict[str, Any]] = None,
        projection: Optional[dict[str, Any]] = None,
    ) -> None:
        self.uri = uri
        self.database = database
        self.collection = collection
        self.filter = filter or {}
        self.projection = projection

    def __iter__(self) -> Iterator[dict[str, Any]]:
        # Imported inside __iter__ so users without the `mongodb` extra
        # installed don't pay the import cost when the package loads.
        from pymongo import MongoClient

        client = MongoClient(self.uri)
        try:
            cursor = client[self.database][self.collection].find(
                self.filter, self.projection
            )
            for doc in cursor:
                yield doc
        finally:
            client.close()
