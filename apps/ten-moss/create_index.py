"""Build the demo Moss index for the ten-moss voice assistant.

Reads documents from ``data/knowledge.jsonl`` and creates the cloud index named
by ``MOSS_INDEX_NAME``. The running agent opens a Moss session on that index.

Usage (from ``apps/ten-moss/``):
    cp .env.example .env    # fill in MOSS_PROJECT_ID / MOSS_PROJECT_KEY / MOSS_INDEX_NAME
    python create_index.py
"""

import asyncio
import json
import os
import pathlib

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

DATA = pathlib.Path(__file__).parent / "data" / "knowledge.jsonl"


def load_documents() -> list[DocumentInfo]:
    """Parse ``data/knowledge.jsonl`` into Moss documents."""
    docs: list[DocumentInfo] = []
    for line in DATA.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        docs.append(
            DocumentInfo(id=row["id"], text=row["text"], metadata=row.get("metadata", {}))
        )
    return docs


async def main() -> None:
    """Create the MOSS_INDEX_NAME index from the sample knowledge base."""
    load_dotenv()
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    index_name = os.environ["MOSS_INDEX_NAME"]
    docs = load_documents()
    print(f"Creating index '{index_name}' with {len(docs)} documents...")
    await client.create_index(name=index_name, docs=docs, model_id="moss-minilm")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
