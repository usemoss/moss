"""Build the Moss knowledge base for the mortgage lending voice agent.

The retrieval agent queries this index for sub-10ms answers about loan
products, eligibility, documentation, and closing costs.

Documents live in `mortgage_kb.json` so they can be edited without touching
this script. Run once before starting the agent:

    uv run python create_index.py
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

load_dotenv()

KB_PATH = Path(__file__).parent / "mortgage_kb.json"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_documents(path: Path = KB_PATH) -> list[DocumentInfo]:
    """Read the JSON knowledge base and return Moss DocumentInfo objects."""
    with path.open() as f:
        raw = json.load(f)
    return [
        DocumentInfo(
            id=doc["id"],
            text=doc["text"],
            metadata=doc.get("metadata", {}),
        )
        for doc in raw
    ]


async def main() -> None:
    project_id = _require_env("MOSS_PROJECT_ID")
    project_key = _require_env("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME", "mortgage-lending-kb")

    docs = load_documents()
    client = MossClient(project_id, project_key)
    print(f"Creating Moss index '{index_name}' with {len(docs)} documents from {KB_PATH.name}...")
    await client.create_index(index_name, docs)
    print(f"Done. Index '{index_name}' is ready for the voice agent.")


if __name__ == "__main__":
    asyncio.run(main())
