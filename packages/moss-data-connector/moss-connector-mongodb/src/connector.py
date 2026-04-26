"""MongoDB connector.

Reads documents from a MongoDB collection via pymongo's `find()`. One yielded
`DocumentInfo` per document.

Note on ids: MongoDB's `_id` comes back as a `bson.ObjectId`. In your `mapper`,
wrap it with `str()` to render the hex string, e.g.
`DocumentInfo(id=str(r["_id"]), ...)`.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator, Optional

from moss import DocumentInfo
from pymongo import MongoClient


class MongoDBConnector:
    """Read documents from a MongoDB collection and yield one `DocumentInfo` per document.

    By default yields every document in the collection. Pass `filter` to
    restrict results (any standard Mongo query dict). Pass `projection` to
    limit which fields come back.

    `mapper` turns a Mongo document (dict) into a `DocumentInfo`.
    """

    def __init__(
        self,
        uri: str,
        database: str,
        collection: str,
        mapper: Callable[[dict[str, Any]], DocumentInfo],
        filter: Optional[dict[str, Any]] = None,
        projection: Optional[dict[str, Any]] = None,
    ) -> None:
        self.uri = uri
        self.database = database
        self.collection = collection
        self.mapper = mapper
        self.filter = filter or {}
        self.projection = projection

    def __iter__(self) -> Iterator[DocumentInfo]:
        client = MongoClient(self.uri)
        try:
            cursor = client[self.database][self.collection].find(
                self.filter, self.projection
            )
            for doc in cursor:
                yield self.mapper(doc)
        finally:
            client.close()
