"""Build the demo Moss index for the Agora custom-llm sample.

Same 10 FAQs as apps/ten-moss/data/knowledge.jsonl so the bench is shared.

Usage (from apps/agora-custom-llm-moss/):
    cp server/.env.example server/.env
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
    """Parse data/knowledge.jsonl into Moss documents."""
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
    load_dotenv(pathlib.Path(__file__).parent / "server" / ".env")
    load_dotenv()
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    index_name = os.environ["MOSS_INDEX_NAME"]
    docs = load_documents()
    print(f"Creating index '{index_name}' with {len(docs)} documents...")
    model_id = os.getenv("MOSS_MODEL_ID", "moss-minilm")
    await client.create_index(name=index_name, docs=docs, model_id=model_id)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
