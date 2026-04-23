"""Template connector package.

Copy this directory to `packages/moss-data-connector/moss-connector-<source>/`,
then rename `TemplateConnector` in `connector.py` to `<Source>Connector`.
"""

from .connector import TemplateConnector
from .ingest import ingest

__all__ = ["TemplateConnector", "ingest"]
