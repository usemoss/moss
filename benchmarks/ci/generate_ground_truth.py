#!/usr/bin/env python3
"""Generate ground truth for CI benchmark recall computation.

Queries the Moss index with a large top_k and records the returned document
IDs as the "expected" set for each benchmark query.  Run this once (or
whenever the index/model changes) and commit the output.

.. note::
   This is a **ranking-stability reference**, not an independent relevance
   judgment: the expected IDs come from Moss itself at a known-good commit.
   The recall gate therefore detects *changes in retrieval behavior* (the
   goal of a regression guard), and will also flag intentional relevance
   improvements — regenerate and commit a new ground truth in that case.

Usage::

    # Ensure MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set
    python benchmarks/ci/generate_ground_truth.py

    # After a corpus or model change, rebuild the index first:
    python benchmarks/ci/generate_ground_truth.py --recreate

Output is written to ``benchmarks/ci/ground_truth.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from bench_queries import DOC_COUNT, INDEX_NAME_DEFAULT, MODEL_ID, QUERIES

load_dotenv()

# Fetch a generous top_k so recall@5 and recall@10 can be evaluated
# against a superset of relevant results.
GROUND_TRUTH_TOP_K = 50


async def _create_index(client, index_name: str) -> None:
    from moss import DocumentInfo

    corpus_path = Path(__file__).resolve().parent.parent / "bench_100k_docs.json"
    if not corpus_path.exists():
        print(f"Error: Corpus file not found: {corpus_path}")
        sys.exit(1)
    with open(corpus_path) as f:
        all_docs = json.load(f)
    docs = [
        DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata"))
        for d in all_docs[:DOC_COUNT]
    ]
    result = await client.create_index(index_name, docs, MODEL_ID)
    print(f"Created index '{index_name}' with {result.doc_count} docs")


async def main(recreate: bool) -> None:
    from moss import MossClient, QueryOptions

    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME", INDEX_NAME_DEFAULT)

    if not project_id or not project_key:
        print("Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set.")
        sys.exit(1)

    client = MossClient(project_id, project_key)

    # Determine existence explicitly (rather than treating any get_index
    # failure as "missing") so auth/network errors surface instead of
    # silently triggering index creation.
    existing = {idx.name for idx in await client.list_indexes()}

    if index_name in existing and recreate:
        print(f"--recreate: deleting existing index '{index_name}'")
        await client.delete_index(index_name)
        existing.discard(index_name)

    if index_name in existing:
        print(f"Using existing index '{index_name}'")
    else:
        await _create_index(client, index_name)

    await client.load_index(index_name)

    # Query each benchmark query with a large top_k.
    ground_truth: dict[str, list[str]] = {}
    for q in QUERIES:
        result = await client.query(
            index_name,
            q,
            QueryOptions(top_k=GROUND_TRUTH_TOP_K, alpha=1),
        )
        doc_ids = [doc.id for doc in result.docs]
        ground_truth[q] = doc_ids
        print(f"  '{q}' → {len(doc_ids)} results")

    output = {
        "model": MODEL_ID,
        "top_k": GROUND_TRUTH_TOP_K,
        "index_name": index_name,
        "doc_count": DOC_COUNT,
        "queries": ground_truth,
    }

    output_path = Path(__file__).resolve().parent / "ground_truth.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nGround truth written to: {output_path}")
    print(f"Queries: {len(ground_truth)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the benchmark index from the corpus before "
        "querying. Required after a corpus or embedding-model change so the "
        "ground truth reflects the current data.",
    )
    args = parser.parse_args()
    asyncio.run(main(recreate=args.recreate))
