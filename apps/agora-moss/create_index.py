"""Seed the Moss index used by the agora-moss demo.

Usage:

    uv run python create_index.py

Reads ``moss_docs.json`` and uploads to the index named ``$MOSS_INDEX_NAME``.
Creates the index if it does not exist; no-ops if it does (idempotent).
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

    logger.info("Ensuring index {!r} exists", index_name)
    try:
        await client.create_index(index_name)
        logger.info("Created index {!r}", index_name)
    except Exception as e:
        # Moss raises on duplicate index creation; treat as idempotent success.
        logger.info("create_index({!r}) -> {}: assuming index already exists", index_name, e)

    logger.info("Uploading {} documents to {!r}", len(raw_docs), index_name)
    documents = [
        DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata", {}))
        for d in raw_docs
    ]
    await client.add_docs(index_name, documents)
    logger.info("Done. Wait a few seconds for the index to finish processing.")


if __name__ == "__main__":
    asyncio.run(main())
