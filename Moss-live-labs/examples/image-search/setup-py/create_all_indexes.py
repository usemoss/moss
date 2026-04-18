"""Creates Moss indexes for all four COCO tiers sequentially.

Requires MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env.
Data files (coco-data-*.json) must exist — run download_coco.py first.
"""

from __future__ import annotations

import asyncio

from pathlib import Path

from dotenv import load_dotenv

from create_index import VALID_TIERS, create_index_for_tier

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def create_all_indexes() -> None:
    """Create indexes for all tiers."""
    print("Creating indexes for all tiers...\n")

    for tier in VALID_TIERS:
        print(f"\n--- Tier: {tier} ---")
        try:
            await create_index_for_tier(tier)
        except (RuntimeError, FileNotFoundError, ValueError, EnvironmentError) as error:
            print(f"Failed to create index for tier {tier}: {error}")

    print("\nAll indexes created.")


if __name__ == "__main__":
    asyncio.run(create_all_indexes())
