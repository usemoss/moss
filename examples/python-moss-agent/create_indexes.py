"""Build the three Moss indexes the ecommerce-support voice agent queries.

The agent's `prewarm()` warms these three indexes into the process cache
once, then every room handler queries them via `attach(ctx)` -> `MossCall`.

Run once before starting the agent:

    uv run python create_indexes.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from moss_agent import DocumentInfo, MossAgent

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"

INDEXES: dict[str, str] = {
    "ecommerce_products": "product_catalog.json",
    "ecommerce_faq": "faq.json",
    "ecommerce_policies": "policies.json",
}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_documents(filename: str) -> list[DocumentInfo]:
    path = DATA_DIR / filename
    with path.open() as f:
        raw = json.load(f)
    docs: list[DocumentInfo] = []
    for doc in raw:
        # Moss requires string-valued metadata. Coerce so the JSON can
        # still write ints/bools naturally (e.g., "price_usd": 279).
        metadata = {k: str(v) for k, v in doc.get("metadata", {}).items()}
        docs.append(
            DocumentInfo(id=doc["id"], text=doc["text"], metadata=metadata)
        )
    return docs


async def main() -> None:
    agent = MossAgent(
        project_id=_require_env("MOSS_PROJECT_ID"),
        project_key=_require_env("MOSS_PROJECT_KEY"),
    )

    for index_name, filename in INDEXES.items():
        docs = load_documents(filename)
        print(f"Creating Moss index '{index_name}' with {len(docs)} documents from {filename}...")
        await agent.create_index(index_name, docs)
        print(f"  done: '{index_name}'")

    print("\nAll three indexes are ready. Start the agent with:")
    print("    uv run python agent.py console")


if __name__ == "__main__":
    asyncio.run(main())
