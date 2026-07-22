"""CI Benchmark Suite — Latency and Recall for Moss.

Runs a fixed query set against a Moss index and records:
  - p50 / p95 / p99 / mean latency (ms)
  - recall@5 and recall@10 vs pre-computed ground truth

Results are written to a JSON file (``--benchmark-output``) and optionally
compared against a checked-in baseline (``--baseline-file``) to catch
performance regressions.

Usage::

    pytest benchmarks/ci/ -v \
        --benchmark-output=benchmark_results.json \
        --baseline-file=benchmarks/ci/baseline.json
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv

from bench_queries import DOC_COUNT, INDEX_NAME_DEFAULT, MODEL_ID, QUERIES

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CI_DIR = Path(__file__).resolve().parent

# DOC_COUNT (1K subset of the full 100K corpus, for CI speed), the query set,
# and the model id are shared with generate_ground_truth.py via bench_queries.
TOP_K_LATENCY = 5
TOP_K_RECALL_5 = 5
TOP_K_RECALL_10 = 10
WARMUP_ROUNDS = 3
QUERY_ROUNDS = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(values: list[float], p: float) -> float:
    """Compute the *p*-th percentile from a **sorted** list of values."""
    if not values:
        return 0.0
    idx = max(int(math.ceil(p * len(values))) - 1, 0)
    return values[idx]


_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """Run *coro* on a single shared event loop.

    ``asyncio.get_event_loop()`` is deprecated (and raises on Python 3.14)
    when no loop is running; ``asyncio.run()`` would create a fresh loop per
    call, breaking clients that bind connections to the first loop. A single
    explicit loop shared across the session avoids both problems.
    """
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


def _git_sha() -> str:
    """Return the short git SHA of HEAD, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def moss_client():
    """Create a MossClient and load the benchmark index once per session."""
    # Import lazily — Moss native bindings may not be installed in every env.
from moss import MossClient, DocumentInfo

    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        pytest.skip("MOSS_PROJECT_ID / MOSS_PROJECT_KEY not set — skipping benchmarks")

    client = MossClient(project_id, project_key)
    index_name = os.getenv("MOSS_INDEX_NAME", INDEX_NAME_DEFAULT)

    async def _setup():
        # Determine existence explicitly (rather than treating any get_index
        # failure as "missing") so auth/network errors surface instead of
        # silently triggering index creation.
        existing = {idx.name for idx in await client.list_indexes()}
        if index_name not in existing:
            # Load documents from the shared corpus file.
            corpus_path = CI_DIR.parent / "bench_100k_docs.json"
            if not corpus_path.exists():
                pytest.skip(f"Corpus file not found: {corpus_path}")
            with open(corpus_path) as f:
                all_docs = json.load(f)
            docs = [
                DocumentInfo(
                    id=d["id"],
                    text=d["text"],
                    metadata=d.get("metadata"),
                )
                for d in all_docs[:DOC_COUNT]
            ]
            await client.create_index(index_name, docs, MODEL_ID)

        await client.load_index(index_name)
        return client, index_name

    client, index_name = _run(_setup())
    yield client, index_name


@pytest.fixture(scope="session")
def ground_truth() -> dict[str, list[str]]:
    """Load pre-computed ground truth document IDs per query."""
    gt_path = CI_DIR / "ground_truth.json"
    if not gt_path.exists():
        pytest.skip(f"Ground truth file not found: {gt_path}")
    with open(gt_path) as f:
        data = json.load(f)
    return data.get("queries", {})


@pytest.fixture(scope="session")
def benchmark_results() -> dict:
    """Mutable dict that accumulates results across tests in this session.

    The ``test_write_results`` finalizer serializes this to JSON.
    """
    return {
        "commit": _git_sha(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "doc_count": DOC_COUNT,
            "query_rounds": QUERY_ROUNDS,
            "warmup_rounds": WARMUP_ROUNDS,
            "top_k_latency": TOP_K_LATENCY,
        },
        "latency_ms": {},
        "recall": {},
    }


# ---------------------------------------------------------------------------
# Tests — pytest collects these in declaration order (measure → guard →
# write). The ordering is a soft dependency only: the guard and writer
# degrade gracefully (skip / write partial results) if measurement data is
# missing, so a random-ordering plugin breaks nothing, it just skips checks.
# ---------------------------------------------------------------------------


class TestBenchmarkLatency:
    """Measure end-to-end query latency over multiple rounds."""

    def test_latency(self, moss_client, benchmark_results):
        from moss import QueryOptions

        client, index_name = moss_client
        latencies: list[float] = []

        async def _measure():
            # Warmup
            for _ in range(WARMUP_ROUNDS):
                for q in QUERIES:
                    await client.query(
                        index_name, q, QueryOptions(top_k=TOP_K_LATENCY, alpha=1)
                    )

            # Measured rounds
            for _ in range(QUERY_ROUNDS):
                for q in QUERIES:
                    start = time.perf_counter()
                    await client.query(
                        index_name, q, QueryOptions(top_k=TOP_K_LATENCY, alpha=1)
                    )
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed_ms)

        _run(_measure())

        latencies.sort()
        result = {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "p99": round(_percentile(latencies, 0.99), 3),
            "mean": round(statistics.mean(latencies), 3),
            "stdev": round(statistics.stdev(latencies), 3) if len(latencies) >= 2 else 0.0,
            "count": len(latencies),
        }
        benchmark_results["latency_ms"] = result

        # Print for CI logs
        print(f"\n  Latency ({len(latencies)} measurements):")
        print(f"    P50  : {result['p50']:.3f} ms")
        print(f"    P95  : {result['p95']:.3f} ms")
        print(f"    P99  : {result['p99']:.3f} ms")
        print(f"    Mean : {result['mean']:.3f} ms")
        print(f"    Stdev: {result['stdev']:.3f} ms")


class TestBenchmarkRecall:
    """Measure recall@k against pre-computed ground truth."""

    def test_recall(self, moss_client, ground_truth, benchmark_results):
        from moss import QueryOptions

        client, index_name = moss_client

        recall_at_5_scores: list[float] = []
        recall_at_10_scores: list[float] = []

        async def _evaluate():
            for q in QUERIES:
                expected_ids = ground_truth.get(q, [])
                if not expected_ids:
                    continue

                # recall@10 — fetch 10 results, also compute recall@5
                result = await client.query(
                    index_name, q, QueryOptions(top_k=TOP_K_RECALL_10, alpha=1)
                )
                returned_ids = [doc.id for doc in result.docs]

                # recall@5
                expected_5 = set(expected_ids[:TOP_K_RECALL_5])
                returned_5 = set(returned_ids[:TOP_K_RECALL_5])
                if expected_5:
                    recall_at_5_scores.append(
                        len(expected_5 & returned_5) / len(expected_5)
                    )

                # recall@10
                expected_10 = set(expected_ids[:TOP_K_RECALL_10])
                returned_10 = set(returned_ids[:TOP_K_RECALL_10])
                if expected_10:
                    recall_at_10_scores.append(
                        len(expected_10 & returned_10) / len(expected_10)
                    )

        _run(_evaluate())

        recall_5 = round(statistics.mean(recall_at_5_scores), 4) if recall_at_5_scores else 0.0
        recall_10 = round(statistics.mean(recall_at_10_scores), 4) if recall_at_10_scores else 0.0

        benchmark_results["recall"] = {
            "recall_at_5": recall_5,
            "recall_at_10": recall_10,
            "queries_evaluated": len(recall_at_5_scores),
        }

        print(f"\n  Recall ({len(recall_at_5_scores)} queries evaluated):")
        print(f"    Recall@5  : {recall_5:.4f}")
        print(f"    Recall@10 : {recall_10:.4f}")


class TestRegressionGuard:
    """Compare current run against the checked-in baseline."""

    def test_no_latency_regression(self, request, benchmark_results):
        baseline_path = request.config.getoption("--baseline-file")
        threshold = request.config.getoption("--latency-threshold")

        if not baseline_path or not Path(baseline_path).exists():
            pytest.skip("No baseline file provided — skipping regression check")

        with open(baseline_path) as f:
            baseline = json.load(f)

        baseline_p95 = baseline.get("latency_ms", {}).get("p95")
        current_p95 = benchmark_results.get("latency_ms", {}).get("p95")

        if baseline_p95 is None or current_p95 is None:
            pytest.skip("Latency data not yet available — run latency test first")

        if baseline_p95 == 0:
            pytest.skip("Baseline p95 is zero — cannot compute regression ratio")

        regression = (current_p95 - baseline_p95) / baseline_p95

        print(f"\n  Latency regression check:")
        print(f"    Baseline P95 : {baseline_p95:.3f} ms")
        print(f"    Current  P95 : {current_p95:.3f} ms")
        print(f"    Change       : {regression:+.1%}")
        print(f"    Threshold    : {threshold:.0%}")

        assert regression <= threshold, (
            f"P95 latency regressed by {regression:+.1%} "
            f"(baseline={baseline_p95:.3f}ms, current={current_p95:.3f}ms, "
            f"threshold={threshold:.0%})"
        )

    def test_no_recall_regression(self, request, benchmark_results):
        baseline_path = request.config.getoption("--baseline-file")
        threshold = request.config.getoption("--recall-threshold")

        if not baseline_path or not Path(baseline_path).exists():
            pytest.skip("No baseline file provided — skipping regression check")

        with open(baseline_path) as f:
            baseline = json.load(f)

        baseline_recall = baseline.get("recall", {}).get("recall_at_5")
        current_recall = benchmark_results.get("recall", {}).get("recall_at_5")

        if baseline_recall is None or current_recall is None:
            pytest.skip("Recall data not yet available — run recall test first")

        drop = baseline_recall - current_recall

        print(f"\n  Recall regression check:")
        print(f"    Baseline Recall@5 : {baseline_recall:.4f}")
        print(f"    Current  Recall@5 : {current_recall:.4f}")
        print(f"    Drop              : {drop:+.4f}")
        print(f"    Threshold         : {threshold:.4f}")

        assert drop <= threshold, (
            f"Recall@5 dropped by {drop:.4f} "
            f"(baseline={baseline_recall:.4f}, current={current_recall:.4f}, "
            f"threshold={threshold:.4f})"
        )


class TestWriteResults:
    """Serialize benchmark results to JSON (always runs last)."""

    def test_write_results(self, request, benchmark_results):
        output_path = request.config.getoption("--benchmark-output")
        with open(output_path, "w") as f:
            json.dump(benchmark_results, f, indent=2)
        print(f"\n  Results written to: {output_path}")
