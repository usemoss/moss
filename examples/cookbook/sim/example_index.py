"""One-time script: index a directory of text/markdown files into Moss.

Usage:
    python example_index.py --docs ./docs --index sim-docs

This creates (or updates) a Moss index named `sim-docs` from all .txt and .md
files under the given directory. Run it once before starting server.py.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

load_dotenv()


async def index_docs(docs_dir: str, index_name: str) -> None:
    """Walk docs_dir and upsert all .txt and .md files into a Moss index."""
    client = MossClient(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
    )

    docs: list[DocumentInfo] = []
    root = Path(docs_dir)
    for path in sorted(root.rglob("*")):
        if path.suffix not in {".txt", ".md"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        rel = str(path.relative_to(root))
        docs.append(
            DocumentInfo(
                id=rel,
                text=text,
                metadata={"source": rel},
            )
        )
        print(f"  queued: {rel} ({len(text)} chars)")

    if not docs:
        print("No documents found — nothing to index.")
        return

    print(f"\nIndexing {len(docs)} document(s) into '{index_name}'...")
    result = await client.create_index(name=index_name, docs=docs)
    print(f"Done. job_id={result.job_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index local docs into a Moss index.")
    parser.add_argument("--docs", default="./docs", help="Directory of .txt/.md files")
    parser.add_argument("--index", default="sim-docs", help="Moss index name")
    args = parser.parse_args()
    asyncio.run(index_docs(args.docs, args.index))


if __name__ == "__main__":
    main()
