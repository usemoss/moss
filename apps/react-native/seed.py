"""
Emoji Search Seeder
Downloads badrex/LLM-generated-emoji-descriptions from HuggingFace (via the
datasets library — uses parquet, no rate limits) and indexes all 5,034 emojis
into a Moss index ready for the React Native app to query.

Usage:
    pip install datasets python-dotenv moss
    python seed.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from datasets import load_dataset
from moss import MossClient, DocumentInfo

load_dotenv()

INDEX_NAME = "emoji-search-v1"


async def main() -> None:
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")

    if not project_id or not project_key:
        print("Error: set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env")
        sys.exit(1)

    print("Downloading emoji dataset from HuggingFace (parquet, cached after first run)…")
    ds = load_dataset("badrex/LLM-generated-emoji-descriptions", split="train")
    print(f"Downloaded {len(ds)} emojis.")

    docs: list[DocumentInfo] = []
    for row in ds:
        tags = ", ".join(row["tags"])
        docs.append(
            DocumentInfo(
                id=row["unicode"],
                # Rich text for embedding: name + LLM description + tags
                text=f"{row['short description']}. {row['LLM description']}. Tags: {tags}",
                metadata={
                    "character":   row["character"],
                    "name":        row["short description"],
                    "description": row["LLM description"],
                    "tags":        tags,
                    "unicode":     row["unicode"],
                },
            )
        )

    client = MossClient(project_id, project_key)

    # Remove any stale index from a previous run
    try:
        await client.delete_index(INDEX_NAME)
        print(f"Deleted existing index '{INDEX_NAME}'.")
    except Exception:
        pass

    print(f"Indexing {len(docs)} emojis into '{INDEX_NAME}' (model: moss-minilm)…")
    await client.create_index(INDEX_NAME, docs, "moss-minilm")
    print(f"✅  Done — index '{INDEX_NAME}' is ready.")


if __name__ == "__main__":
    asyncio.run(main())
