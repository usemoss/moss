#!/usr/bin/env python3
"""Generate ground truth for CI benchmark recall computation.

Queries the Moss index with a large top_k and records the returned document
IDs as the "expected" relevant set for each benchmark query.  Run this once
(or whenever the index/model changes) and commit the output.

Usage::

    # Ensure MOSS_PROJECT_ID and MOSS_PROJECT_KEY are set
    python benchmarks/ci/generate_ground_truth.py

Output is written to ``benchmarks/ci/ground_truth.json``.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Re-use the same query set as the CI benchmark.
QUERIES = [
    "neural network training data",
    "anomaly detection patterns",
    "computer vision image processing",
    "natural language processing",
    "reinforcement learning rewards",
    "transfer learning pretrained models",
    "distributed computing systems",
    "cryptographic data encryption",
    "database indexing performance",
    "knowledge graph entities",
    "generative adversarial networks",
    "attention mechanism transformers",
    "dimensionality reduction compression",
    "federated learning privacy",
    "stream processing pipelines",
]

# Fetch a generous top_k so recall@5 and recall@10 can be evaluated
# against a superset of relevant results.
GROUND_TRUTH_TOP_K = 50


async def main() -> None:
    from moss import MossClient, DocumentInfo, QueryOptions

    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME", "benchmark-ci")

    if not project_id or not project_key:
        print("Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set.")
        sys.exit(1)

    client = MossClient(project_id, project_key)

    # Ensure the index exists (create with a 1K subset if needed).
    try:
        await client.get_index(index_name)
        print(f"Using existing index '{index_name}'")
    except Exception:
        corpus_path = Path(__file__).resolve().parent.parent / "bench_100k_docs.json"
        if not corpus_path.exists():
            print(f"Error: Corpus file not found: {corpus_path}")
            sys.exit(1)
        with open(corpus_path) as f:
            all_docs = json.load(f)
        docs = [
            DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata"))
            for d in all_docs[:1000]
        ]
        result = await client.create_index(index_name, docs, "moss-minilm")
        print(f"Created index '{index_name}' with {result.doc_count} docs")

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
        "model": "moss-minilm",
        "top_k": GROUND_TRUTH_TOP_K,
        "index_name": index_name,
        "doc_count": 1000,
        "queries": ground_truth,
    }

    output_path = Path(__file__).resolve().parent / "ground_truth.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nGround truth written to: {output_path}")
    print(f"Queries: {len(ground_truth)}")


if __name__ == "__main__":
    asyncio.run(main())
