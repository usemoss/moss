"""Loads a tiered Moss index and performs a sample search query.

Set MOSS_INDEX_TIER in .env to choose the tier (default: 1k).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from inferedge_moss import MossClient
from moss_core import QueryOptions

TOP_K = 10

SAMPLE_QUERIES = [
    "a dog catching a frisbee in mid-air",
    "people riding bikes down a city street",
    "a cat sitting on a laptop keyboard",
    "a large pizza on a wooden table",
    "surfers riding waves at the beach",
]


async def load_and_query_sample() -> None:
    """Load an existing image index and execute a sample hybrid query."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    base_index_name = os.getenv("MOSS_INDEX_NAME")
    tier = os.getenv("MOSS_INDEX_TIER", "1k")

    if not project_id or not project_key or not base_index_name:
        print("Error: Missing required environment variables!")
        print("Set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env")
        return

    index_name = f"{base_index_name}-{tier}"

    print("=" * 40)
    print("Moss SDK - Search Query Sample")
    print("=" * 40)
    print(f"Using index: {index_name} (tier: {tier})")

    client = MossClient(project_id, project_key)

    try:
        print("\nLoading index...")
        await client.load_index(index_name)
        print("Index loaded successfully")
        print("=" * 40)

        for query in SAMPLE_QUERIES:
            print(f"\nPerforming search for: \"{query}\"\n")
            results = await client.query(index_name, query, QueryOptions(top_k=TOP_K))

            print(f"Found {len(results.docs)} results in {results.time_taken_ms}ms\n")
            for idx, doc in enumerate(results.docs, 1):
                print(f"[{doc.id}] Result {idx}")
                print(f"Score: {doc.score:.3f}")
                print(f"Snippet: {doc.text}\n")

        print("All queries completed successfully!")

    except RuntimeError as error:
        print(f"Error: {error}")
        print("Check your credentials and index configuration.")


if __name__ == "__main__":
    asyncio.run(load_and_query_sample())
