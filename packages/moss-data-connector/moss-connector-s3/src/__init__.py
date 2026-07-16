"""Amazon S3 connector package.

Reads objects from an S3 bucket into a Moss index, with an optional
``watch()`` loop that re-indexes whenever the bucket contents change.
"""

from .connector import S3Connector
from .ingest import ingest
from .watch import watch

__all__ = ["S3Connector", "ingest", "watch"]
