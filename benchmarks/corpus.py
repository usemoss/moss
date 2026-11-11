"""Fixed local corpus and queries, plus the legacy cloud corpus loader."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

FIXED_CORPUS_PATH = Path(__file__).resolve().parent / "bench_100k_docs.json"
FIXED_CORPUS_SHA256 = (
    "1f2424e76ac6c768b36ced84f9244d810414e0671a33fd2f8bf9e7329ed0da04"
)

QUERIES = [
    "neural network training data",
    "anomaly detection patterns",
    "computer vision image processing",
    "natural language processing",
    "reinforcement learning rewards",
    "transfer learning pretrained models",
    "distributed computing systems",
    "cryptographic data encryption",
    "database indexing performance",
    "knowledge graph entities",
    "generative adversarial networks",
    "attention mechanism transformers",
    "dimensionality reduction compression",
    "federated learning privacy",
    "stream processing pipelines",
]


def get_documents(count=100_000):
    """Fetch *count* documents from the Moss index."""
    docs = fetch_docs_from_moss()
    return docs[:count] if count < len(docs) else docs


def get_queries():
    """Return the fixed set of 15 test queries."""
    return list(QUERIES)


def load_fixed_documents(path=None, expected_count=100_000):
    """Return validated records and the SHA-256 of their exact source bytes.

    The checked-in corpus must retain its known checksum. An explicit
    alternative path permits small offline test fixtures, whose checksum is
    still calculated and reported rather than assumed to match the full set.
    """
    selected = Path(path) if path is not None else FIXED_CORPUS_PATH
    raw = selected.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if selected.resolve() == FIXED_CORPUS_PATH.resolve():
        if digest != FIXED_CORPUS_SHA256:
            raise ValueError("Fixed benchmark corpus checksum mismatch")
    documents = json.loads(raw)
    if not isinstance(documents, list) or len(documents) != expected_count:
        raise ValueError(f"Expected exactly {expected_count} corpus documents")
    seen = set()
    for row in documents:
        if not isinstance(row, dict):
            raise ValueError("Every corpus document must be an object")
        doc_id = row.get("id")
        text = row.get("text")
        if not isinstance(doc_id, str) or not doc_id.strip():
            raise ValueError("Every corpus document needs a nonempty string ID")
        if doc_id in seen:
            raise ValueError("Corpus document IDs must be unique")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Every corpus document needs nonempty string text")
        seen.add(doc_id)
    return documents, digest


# ---------------------------------------------------------------------------
# Fetch real documents from a Moss index
# ---------------------------------------------------------------------------

def fetch_docs_from_moss():
    """Fetch all documents from the Moss index specified by MOSS_INDEX_NAME."""
    from dotenv import load_dotenv

    load_dotenv()
    index_name = os.getenv("MOSS_INDEX_NAME")
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not all([index_name, project_id, project_key]):
        raise ValueError(
            "MOSS_INDEX_NAME, MOSS_PROJECT_ID, and MOSS_PROJECT_KEY must be set "
            "in .env to fetch docs from Moss"
        )

    return asyncio.run(
        _fetch_moss_docs(index_name, project_id, project_key)
    )


async def _fetch_moss_docs(index_name, project_id, project_key):
    from moss import MossClient

    client = MossClient(project_id, project_key)
    print(f"  Fetching docs from Moss index '{index_name}'...")
    moss_docs = await client.get_docs(index_name)
    print(f"  Fetched {len(moss_docs)} docs")
    return [
        {
            "id": d.id,
            "text": d.text,
            "metadata": dict(d.metadata) if d.metadata else {},
        }
        for d in moss_docs
    ]
