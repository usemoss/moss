"""Amazon S3 connector package.

Reads objects from an S3 bucket into a Moss index, with an optional
``watch()`` loop that re-indexes whenever the bucket contents change.
"""

from .aio import ingest
from .connector import S3Connector
from .watch import watch

__all__ = ["S3Connector", "ingest", "watch"]
