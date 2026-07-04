"""
create_index.py – Bharat Benefits Voice Agent
==============================================
Reads all markdown files from data/schemes/, creates a Moss index, and
populates it with the scheme documents.

Usage:
    python create_index.py

Environment variables (via .env):
    MOSS_PROJECT_ID   – your Moss project ID
    MOSS_PROJECT_KEY  – your Moss project key
    MOSS_INDEX_NAME   – index name (default: bharat-benefits)
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment
load_dotenv()

MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID", "")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY", "")
MOSS_INDEX_NAME = os.getenv("MOSS_INDEX_NAME", "bharat-benefits")

SCHEMES_DIR = Path(__file__).parent / "data" / "schemes"


def _check_env() -> None:
    """Fail fast with a helpful message if credentials are missing."""
    missing = []
    if not MOSS_PROJECT_ID:
        missing.append("MOSS_PROJECT_ID")
    if not MOSS_PROJECT_KEY:
        missing.append("MOSS_PROJECT_KEY")
    if missing:
        print(
            "\n[ERROR] The following environment variables are not set:\n"
            + "\n".join(f"  {v}" for v in missing)
            + "\n\nCopy .env.example -> .env and fill in your Moss credentials."
            "\nGet them at: https://moss.dev\n",
            file=sys.stderr,
        )
        sys.exit(1)


def _load_markdown_files() -> list[dict]:
    """
    Walk SCHEMES_DIR and return a list of document dicts ready for Moss.
    Each dict has: id (filename stem), text (full markdown content), metadata.
    """
    if not SCHEMES_DIR.exists():
        print(
            f"\n[ERROR] Schemes directory not found: {SCHEMES_DIR}\n"
            "Make sure you are running this script from the bharat-benefits/ folder.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    md_files = sorted(SCHEMES_DIR.glob("*.md"))
    if not md_files:
        print(
            f"\n[ERROR] No markdown files found in {SCHEMES_DIR}.\n"
            "Expected files like ayushman-bharat.md, pm-kisan.md, etc.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    docs = []
    for path in md_files:
        text = path.read_text(encoding="utf-8").strip()
        docs.append(
            {
                "id": path.stem,
                "text": text,
                "source": path.name,
            }
        )
    return docs


async def main() -> None:
    _check_env()

    print(f"\nLoading scheme documents from: {SCHEMES_DIR}")
    raw_docs = _load_markdown_files()
    print(f"   Found {len(raw_docs)} file(s):")
    for d in raw_docs:
        print(f"   - {d['source']}")

    # Import Moss SDK
    try:
        from moss import DocumentInfo, MossClient
    except ImportError:
        print(
            "\n[ERROR] moss is not installed.\n"
            "Run:  pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Build Moss DocumentInfo objects
    documents = [
        DocumentInfo(
            id=d["id"],
            text=d["text"],
            metadata={"source": d["source"]},
        )
        for d in raw_docs
    ]

    # Create (or recreate) the Moss index
    print(f"\nCreating Moss index '{MOSS_INDEX_NAME}' ...")
    print(f"   Project ID : {MOSS_PROJECT_ID[:6]}... (truncated for safety)")

    client = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)

    try:
        await client.create_index(MOSS_INDEX_NAME, documents)
    except Exception as exc:
        print(
            f"\n[ERROR] Failed to create Moss index: {exc}\n"
            "Check that your MOSS_PROJECT_ID and MOSS_PROJECT_KEY are correct\n"
            "and that you have internet access.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"\nIndex '{MOSS_INDEX_NAME}' created successfully with {len(documents)} document(s)."
    )
    print("\nNext step: run the bot with -")
    print('  python bot.py --text "I am a small farmer. Which scheme can help me?"\n')


if __name__ == "__main__":
    asyncio.run(main())
