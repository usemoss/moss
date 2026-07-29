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

from bench_queries import (
    DOC_COUNT,
    INDEX_NAME_PREFIX,
    MODEL_ID,
    QUERIES,
    build_fingerprint,
    corpus_signature,
    index_name_for,
    load_corpus_slice,
    query_set_hash,
)
from dotenv import load_dotenv

load_dotenv()

# Fetch a generous top_k so recall@5 and recall@10 can be evaluated
# against a superset of relevant results.
GROUND_TRUTH_TOP_K = 50


def _corpus_slice() -> list[dict]:
    corpus_path = Path(__file__).resolve().parent.parent / "bench_100k_docs.json"
    if not corpus_path.exists():
        print(f"Error: Corpus file not found: {corpus_path}")
        sys.exit(1)
    return load_corpus_slice(corpus_path)


async def _create_index(client, index_name: str, corpus_slice: list[dict]) -> None:
    from moss import DocumentInfo

    docs = [
        DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata"))
        for d in corpus_slice
    ]
    result = await client.create_index(index_name, docs, MODEL_ID)
    print(f"Created index '{index_name}' with {result.doc_count} docs")


def _guard_deletion(index_name: str, derived_name: str, force: bool) -> None:
    """Refuse to delete indexes that are not clearly benchmark-owned.

    MOSS_INDEX_NAME is a documented override, so a developer whose
    environment points at a shared or production Moss project could
    otherwise aim --recreate at a non-benchmark index and destroy it.
    """
    if index_name == derived_name:
        return  # the derived benchmark index — always safe to recreate
    if not index_name.startswith(f"{INDEX_NAME_PREFIX}-"):
        print(
            f"Error: refusing to delete index '{index_name}' — it is outside "
            f"the benchmark namespace ('{INDEX_NAME_PREFIX}-*'). Unset "
            "MOSS_INDEX_NAME or point it at a benchmark index."
        )
        sys.exit(1)
    if not force:
        print(
            f"Error: MOSS_INDEX_NAME overrides the derived name "
            f"('{index_name}' != '{derived_name}'). Pass --force to confirm "
            "deleting the overridden benchmark index."
        )
        sys.exit(1)


async def main(recreate: bool, force: bool, prune: bool) -> dict:
    from moss import MossClient, QueryOptions

    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    # Same derivation as the benchmark tests: the index name embeds the
    # corpus/model signature and the SDK build fingerprint, so generation
    # and evaluation can never target indexes built from different inputs
    # or by different indexing code.
    corpus_slice = _corpus_slice()
    signature = corpus_signature(corpus_slice)
    derived_name = index_name_for(signature, build_fingerprint())
    index_name = os.getenv("MOSS_INDEX_NAME") or derived_name

    if not project_id or not project_key:
        print("Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set.")
        sys.exit(1)

    client = MossClient(project_id, project_key)

    # Determine existence explicitly (rather than treating any get_index
    # failure as "missing") so auth/network errors surface instead of
    # silently triggering index creation.
    existing = {idx.name for idx in await client.list_indexes()}

    if index_name in existing and recreate:
        _guard_deletion(index_name, derived_name, force)
        print(f"--recreate: deleting existing index '{index_name}'")
        await client.delete_index(index_name)
        existing.discard(index_name)

    if index_name in existing:
        print(f"Using existing index '{index_name}'")
    else:
        await _create_index(client, index_name, corpus_slice)

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
        # Validated by the benchmark tests: recall is only evaluated when the
        # current corpus/model signature AND query set match the ones used
        # at generation.
        "signature": signature,
        "query_set": {"hash": query_set_hash(), "count": len(QUERIES)},
        "queries": ground_truth,
    }

    if prune:
        # Old corpus/SDK revisions leave benchmark-ci-* indexes behind;
        # remove everything in the benchmark namespace except the index we
        # just used. Never touches indexes outside the namespace.
        stale = sorted(
            n
            for n in existing
            if n != index_name
            and (n == INDEX_NAME_PREFIX or n.startswith(f"{INDEX_NAME_PREFIX}-"))
        )
        for n in stale:
            print(f"--prune: deleting stale benchmark index '{n}'")
            await client.delete_index(n)
        if not stale:
            print("--prune: no stale benchmark indexes found")

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the benchmark index from the corpus before "
        "querying. Required after a corpus or embedding-model change so the "
        "ground truth reflects the current data.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Confirm --recreate deletion when MOSS_INDEX_NAME overrides the "
        "derived index name. Only benchmark-namespace indexes "
        "(benchmark-ci-*) can be deleted even with this flag.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="After generating, delete leftover benchmark-namespace indexes "
        "(benchmark-ci-*) from earlier corpus/SDK revisions. Indexes outside "
        "the benchmark namespace are never touched.",
    )
    args = parser.parse_args()
    output = asyncio.run(main(recreate=args.recreate, force=args.force, prune=args.prune))

    output_path = Path(__file__).resolve().parent / "ground_truth.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nGround truth written to: {output_path}")
    print(f"Queries: {len(output['queries'])}")
