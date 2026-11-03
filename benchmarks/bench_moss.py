"""Benchmark: Moss — built-in embedding, single-call semantic search.

Moss embeds and searches in a single call. No external embedding
service is needed. This measures true end-to-end latency.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from corpus import get_documents, get_queries
from stats import Timer, BenchmarkResult

DOC_COUNT = 100_000
TOP_K = 5
WARMUP_ROUNDS = 3
QUERY_ROUNDS = 50


@dataclass
class Measurement:
    """The shared workload's statistics, ordered samples, and initial rankings."""

    result: BenchmarkResult
    first_query_ms: float
    latencies_ms: list[float]
    rankings: dict[str, list[str]]


async def measure_queries(
    query_fn: Callable[[str], Awaitable[Any]],
    queries=None,
    *,
    name: str,
    expected_ids=None,
) -> Measurement:
    """Time the legacy workload; local result validation stays outside timers."""
    queries = get_queries() if queries is None else list(queries)
    if not queries or any(not isinstance(q, str) or not q.strip() for q in queries):
        raise ValueError("Benchmark queries must be nonempty strings")
    if len(set(queries)) != len(queries):
        raise ValueError("Benchmark queries must be unique")
    if QUERY_ROUNDS < 1 or WARMUP_ROUNDS < 0 or TOP_K < 1:
        raise ValueError("Invalid benchmark round count or result cutoff")

    def result_ids(hits):
        """Read result IDs and optionally enforce the fixed local-corpus contract."""
        found = [doc.id for doc in hits.docs]
        if expected_ids is not None:
            if len(found) != TOP_K or len(set(found)) != TOP_K:
                raise ValueError(f"Expected {TOP_K} unique query results")
            if any(doc_id not in expected_ids for doc_id in found):
                raise ValueError("Query returned a document outside the fixed corpus")
        return found

    with Timer() as first:
        hits = await query_fn(queries[0])
    if expected_ids is not None:
        result_ids(hits)
    print(f"\n  First query after setup: {first.elapsed_ms:.3f} ms")

    print(f"\n  Warming up ({WARMUP_ROUNDS} rounds)...")
    for _ in range(WARMUP_ROUNDS):
        for query in queries:
            hits = await query_fn(query)
            if expected_ids is not None:
                result_ids(hits)

    print(f"  Measuring ({QUERY_ROUNDS} rounds x {len(queries)} queries)...\n")
    latencies = []
    rankings = {}
    for round_number in range(QUERY_ROUNDS):
        for query in queries:
            with Timer() as timer:
                hits = await query_fn(query)
            latencies.append(timer.elapsed_ms)
            if expected_ids is not None or round_number == 0:
                found = result_ids(hits)
                if round_number == 0:
                    rankings[query] = found

    result = BenchmarkResult(name, latencies)
    if result.count != QUERY_ROUNDS * len(queries):
        raise ValueError("Benchmark did not measure the complete workload")
    print(result.summary())
    return Measurement(result, first.elapsed_ms, latencies, rankings)


async def run_async():
    """Run the original cloud-loaded index benchmark and return its latency stats."""
    from dotenv import load_dotenv
    from moss import MossClient, DocumentInfo, QueryOptions

    load_dotenv()
    queries = get_queries()

    print(f"  docs in index  : {DOC_COUNT}")
    print(f"  warmup rounds  : {WARMUP_ROUNDS}")
    print(f"  query rounds   : {QUERY_ROUNDS}")
    print(f"  queries/round  : {len(queries)}")
    print("  embedding      : built-in (moss-minilm)")

    # --- Setup ---
    client = MossClient(
        os.getenv("MOSS_PROJECT_ID"),
        os.getenv("MOSS_PROJECT_KEY"),
    )

    index_name = os.getenv("MOSS_INDEX_NAME", "benchmark-public")

    # Create index if it doesn't exist, otherwise reuse
    try:
        await client.get_index(index_name)
        print(f"  Reusing existing index '{index_name}'")
    except Exception:
        docs = get_documents(DOC_COUNT)
        moss_docs = [
            DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata"))
            for d in docs
        ]
        result = await client.create_index(index_name, moss_docs, "moss-minilm")
        print(f"  Created index with {result.doc_count} docs")

    # --- Load index locally for in-memory search ---
    print("  Loading index into memory...")
    await client.load_index(index_name)

    async def query(text):
        """Bind the existing index and query options to the shared workload."""
        return await client.query(index_name, text, QueryOptions(top_k=TOP_K, alpha=1))

    measurement = await measure_queries(
        query,
        queries,
        name=f"Moss (built-in embedding, top_k={TOP_K}, {DOC_COUNT} docs)",
    )
    return measurement.result


def run():
    return asyncio.run(run_async())


if __name__ == "__main__":
    run()
