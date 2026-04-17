"""Seed the Moss index used by the agora-moss demo.

Usage:

    uv run python create_index.py

Reads ``moss_docs.json`` and uploads to the index named ``$MOSS_INDEX_NAME``.
Creates the index with documents in a single call; no-ops if the index already
exists (idempotent).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from moss import DocumentInfo, MossClient

REQUIRED_ENV = ("MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME")


async def main() -> None:
    """Seed the configured Moss index from ``moss_docs.json`` (idempotent)."""
    load_dotenv()
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        logger.error("Missing required env vars: {}", ", ".join(missing))
        sys.exit(1)

    index_name = os.environ["MOSS_INDEX_NAME"]
    docs_path = Path(__file__).parent / "moss_docs.json"
    raw_docs = json.loads(docs_path.read_text())

    client = MossClient(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
    )

    documents = [
        DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata", {})) for d in raw_docs
    ]

    logger.info("Creating index {!r} with {} documents", index_name, len(documents))
    try:
        await client.create_index(
            name=index_name,
            docs=documents,
            model_id="moss-minilm",
        )
        logger.info("Created index {!r}", index_name)
    except Exception as e:
        # Moss has no named "duplicate index" error class, so match on message.
        # Any other failure (bad creds, network, validation) should surface.
        if "already exists" not in str(e).lower():
            raise
        logger.info("Index {!r} already exists; skipping creation", index_name)

    logger.info("Done. Wait a few seconds for the index to finish processing.")


if __name__ == "__main__":
    asyncio.run(main())
