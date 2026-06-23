"""HuggingFace Datasets source connector for Moss.

from moss_connector_huggingface import HuggingFaceDatasetConnector, ingest
from moss_connector_huggingface import HuggingFaceLocalDatasetConnector
"""

from .connector import HuggingFaceDatasetConnector, HuggingFaceLocalDatasetConnector, auto_mapper
from .ingest import ingest

__all__ = [
    "HuggingFaceDatasetConnector",
    "HuggingFaceLocalDatasetConnector",
    "auto_mapper",
    "ingest",
]
