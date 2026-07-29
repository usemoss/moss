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
from bench_queries import (
    DOC_COUNT,
    MODEL_ID,
    QUERIES,
    build_fingerprint,
    corpus_signature,
    index_name_for,
    load_corpus_slice,
    query_set_hash,
)
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional outside benchmarks/ci

    def load_dotenv() -> None:
        return None


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
    idx = max(math.ceil(p * len(values)) - 1, 0)
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
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _missing_required_input(message: str):
    """Handle a missing benchmark prerequisite (inputs, measurement data, …).

    Skip on fork PRs (``ALLOW_BENCHMARK_SKIP=1``) and local runs, but FAIL
    in trusted CI — a missing prerequisite must not turn the benchmark
    workflow into a green no-op.
    """
    if os.getenv("ALLOW_BENCHMARK_SKIP") == "1":
        pytest.skip(f"{message} — fork PR, skipping benchmarks")
    if os.getenv("CI"):
        pytest.fail(f"{message} — must not silently pass in a trusted CI run")
    pytest.skip(message)


# Config keys that must match between the current run and the baseline for a
# regression comparison to be meaningful. index_name is excluded: it may be
# overridden via MOSS_INDEX_NAME without changing what is measured.
BASELINE_COMPAT_KEYS = (
    "signature",
    "query_set_hash",
    "doc_count",
    "query_rounds",
    "warmup_rounds",
    "top_k_latency",
)


def _assert_baseline_compatible(baseline: dict, benchmark_results: dict) -> None:
    """Fail when the baseline was captured under different benchmark inputs.

    Comparing against a baseline built from another corpus/model, query set,
    or measurement config silently masks (or fabricates) regressions.
    """
    current = {k: benchmark_results.get("config", {}).get(k) for k in BASELINE_COMPAT_KEYS}
    base = {k: baseline.get("config", {}).get(k) for k in BASELINE_COMPAT_KEYS}
    if base != current:
        diffs = {k: (base[k], current[k]) for k in BASELINE_COMPAT_KEYS if base[k] != current[k]}
        pytest.fail(
            "baseline.json is not comparable to this run — config mismatch "
            f"(baseline vs current): {diffs}. Regenerate the baseline via the "
            "Benchmark workflow with update_baseline=true and commit the artifact."
        )


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def corpus_slice() -> list[dict]:
    """The exact corpus slice the benchmark index is built from."""
    corpus_path = CI_DIR.parent / "bench_100k_docs.json"
    if not corpus_path.exists():
        _missing_required_input(f"Corpus file not found: {corpus_path}")
    return load_corpus_slice(corpus_path)


@pytest.fixture(scope="session")
def corpus_sig(corpus_slice) -> str:
    """Content signature of model + DOC_COUNT + corpus slice."""
    return corpus_signature(corpus_slice)


@pytest.fixture(scope="session")
def build_fp() -> str:
    """Fingerprint of the index build path (SDK versions + source tree)."""
    return build_fingerprint()


@pytest.fixture(scope="session")
def moss_client(corpus_slice, corpus_sig, build_fp):
    """Create a MossClient and load the benchmark index once per session.

    The index name embeds ``corpus_sig`` (corpus/DOC_COUNT/model) AND
    ``build_fp`` (SDK versions + source), so an index built from different
    data or by different indexing code can never be silently reused —
    mismatched inputs produce a different name and the index is (re)created
    from the current corpus by the current code, exercising the full
    create_index/document-serialization path whenever it changes.
    """
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        if os.getenv("ALLOW_BENCHMARK_SKIP") == "1":
            pytest.skip(
                "MOSS_PROJECT_ID / MOSS_PROJECT_KEY not set — fork PR without "
                "secrets, skipping benchmarks"
            )
        if os.getenv("CI"):
            pytest.fail(
                "MOSS_PROJECT_ID / MOSS_PROJECT_KEY are not set in a trusted CI "
                "run — the benchmark workflow would otherwise pass as a green "
                "no-op. Configure the repository secrets, or export "
                "ALLOW_BENCHMARK_SKIP=1 for runs that legitimately lack them."
            )
        pytest.skip("MOSS_PROJECT_ID / MOSS_PROJECT_KEY not set — skipping benchmarks")

    # Import lazily (and only once credentials are known to exist) — Moss
    # native bindings may not be installed in every env.
    from moss import DocumentInfo, MossClient

    index_name = os.getenv("MOSS_INDEX_NAME") or index_name_for(corpus_sig, build_fp)

    async def _setup():
        # Construct the client inside the coroutine, after _run() has
        # created and installed the shared event loop — MossClient may bind
        # an async session or call get_event_loop() internally, and must do
        # so against the loop it will actually run on.
        client = MossClient(project_id, project_key)

        # Determine existence explicitly (rather than treating any get_index
        # failure as "missing") so auth/network errors surface instead of
        # silently triggering index creation.
        existing = {idx.name for idx in await client.list_indexes()}
        if index_name not in existing:
            docs = [
                DocumentInfo(
                    id=d["id"],
                    text=d["text"],
                    metadata=d.get("metadata"),
                )
                for d in corpus_slice
            ]
            await client.create_index(index_name, docs, MODEL_ID)

        await client.load_index(index_name)
        return client, index_name

    client, index_name = _run(_setup())
    yield client, index_name


@pytest.fixture(scope="session")
def ground_truth(corpus_sig) -> dict[str, list[str]]:
    """Load pre-computed ground truth document IDs per query.

    Fails (not skips) when the ground truth was generated from a different
    corpus/model/DOC_COUNT — evaluating recall against mismatched expected
    ids would mask corpus or model regressions.
    """
    gt_path = CI_DIR / "ground_truth.json"
    if not gt_path.exists():
        _missing_required_input(f"Ground truth file not found: {gt_path}")
    with open(gt_path) as f:
        data = json.load(f)
    gt_sig = data.get("signature")
    if gt_sig != corpus_sig:
        pytest.fail(
            f"ground_truth.json signature {gt_sig!r} does not match the current "
            f"corpus/model signature {corpus_sig!r} — the corpus, DOC_COUNT, or "
            "model changed since generation. Regenerate with: "
            "python benchmarks/ci/generate_ground_truth.py --recreate"
        )
    gt_query_hash = data.get("query_set", {}).get("hash")
    if gt_query_hash != query_set_hash():
        pytest.fail(
            f"ground_truth.json query-set hash {gt_query_hash!r} does not match "
            f"the current query set ({query_set_hash()!r}) — QUERIES changed "
            "since generation. Regenerate with: "
            "python benchmarks/ci/generate_ground_truth.py"
        )
    return data.get("queries", {})


@pytest.fixture(scope="session")
def benchmark_results(request, corpus_sig, build_fp) -> dict:
    """Mutable dict that accumulates results across tests in this session.

    Registered on the pytest config so ``pytest_sessionfinish`` (in
    conftest.py) serializes it to JSON after the run — regardless of test
    ordering, ``-x``/``--maxfail``, or guard failures.
    """
    results = {
        "commit": _git_sha(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "doc_count": DOC_COUNT,
            "query_rounds": QUERY_ROUNDS,
            "warmup_rounds": WARMUP_ROUNDS,
            "top_k_latency": TOP_K_LATENCY,
            "signature": corpus_sig,
            "query_set_hash": query_set_hash(),
            "query_count": len(QUERIES),
            "build_fingerprint": build_fp,
            "index_name": os.getenv("MOSS_INDEX_NAME")
            or index_name_for(corpus_sig, build_fp),
        },
        "latency_ms": {},
        "recall": {},
    }
    request.config._benchmark_results = results
    return results


# ---------------------------------------------------------------------------
# Tests — pytest collects these in declaration order (measure → guard).
# Results serialization happens in conftest.pytest_sessionfinish, so the
# artifact is written even under -x/--maxfail, reordering plugins, or guard
# failures. Locally and on fork PRs the guards degrade gracefully (skip)
# when measurement data is missing. In trusted CI the guards FAIL on missing
# measurement data — a regression gate that silently passes without
# measurements is a green no-op — so a random-ordering plugin that runs a
# guard before the measurement tests will fail loudly there, by design.
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
                expected_ids = ground_truth.get(q)
                if not expected_ids:
                    # Silently skipping would shrink the evaluated set and
                    # inflate recall — fail loudly instead.
                    raise AssertionError(
                        f"Ground truth missing results for query {q!r}; "
                        "regenerate benchmarks/ci/ground_truth.json"
                    )

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

        if not baseline_path:
            pytest.skip("No baseline file provided — skipping regression check")
        if not Path(baseline_path).exists():
            # An explicitly requested baseline that is absent is a config
            # error, not an optional feature — never a green skip.
            pytest.fail(f"--baseline-file was provided but does not exist: {baseline_path}")

        with open(baseline_path) as f:
            baseline = json.load(f)

        baseline_p95 = baseline.get("latency_ms", {}).get("p95")
        current_p95 = benchmark_results.get("latency_ms", {}).get("p95")

        if baseline_p95 is None or current_p95 is None:
            # A baseline comparison was requested but there is nothing to
            # compare: fine when measurement legitimately skipped (fork PR /
            # local run without credentials), a red flag in trusted CI.
            _missing_required_input(
                "Latency measurement data missing — the latency test did not run"
            )

        _assert_baseline_compatible(baseline, benchmark_results)

        if baseline.get("latency_guard") == "unarmed":
            # The checked-in placeholder declares itself unarmed: latency
            # baselines must come from CI runners, and none has been captured
            # yet. Skip loudly (recall is still guarded) instead of failing
            # every trusted run until the first artifact lands.
            if baseline_p95 != 0:
                pytest.fail(
                    "baseline.json marks latency_guard as 'unarmed' but contains "
                    "a non-zero p95 — remove the latency_guard flag to arm the "
                    "guard."
                )
            pytest.skip(
                "LATENCY GUARD NOT ARMED — baseline.json is the explicit "
                "placeholder (latency_guard: unarmed). To arm it: download the "
                "benchmark-results-<sha> artifact from a trusted CI run and "
                "commit it as benchmarks/ci/baseline.json (the artifact carries "
                "no latency_guard flag, so committing it arms the guard)."
            )

        if baseline_p95 == 0:
            # Zero without the explicit unarmed marker is a misconfigured
            # baseline, not a placeholder — never a silent pass.
            pytest.fail(
                "Baseline p95 is zero but baseline.json does not declare "
                "latency_guard: unarmed — the baseline is misconfigured. Commit "
                "a CI-captured baseline or restore the explicit placeholder."
            )

        regression = (current_p95 - baseline_p95) / baseline_p95

        print("\n  Latency regression check:")
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

        if not baseline_path:
            pytest.skip("No baseline file provided — skipping regression check")
        if not Path(baseline_path).exists():
            pytest.fail(f"--baseline-file was provided but does not exist: {baseline_path}")

        with open(baseline_path) as f:
            baseline = json.load(f)

        # Guard every recall metric the suite records — checking only
        # recall@5 would let a change that preserves the top 5 but drops
        # documents ranked 6-10 pass while recall@10 regresses.
        recall_pairs: dict[str, tuple[float, float]] = {}
        for key in ("recall_at_5", "recall_at_10"):
            baseline_val = baseline.get("recall", {}).get(key)
            current_val = benchmark_results.get("recall", {}).get(key)
            if baseline_val is None or current_val is None:
                _missing_required_input(
                    f"Recall measurement data missing for {key} — "
                    "the recall test did not run"
                )
            recall_pairs[key] = (baseline_val, current_val)

        _assert_baseline_compatible(baseline, benchmark_results)

        failures: list[str] = []
        print("\n  Recall regression check:")
        print(f"    Threshold: {threshold:.4f}")
        for key, (baseline_val, current_val) in recall_pairs.items():
            drop = baseline_val - current_val
            print(
                f"    {key}: baseline={baseline_val:.4f} "
                f"current={current_val:.4f} drop={drop:+.4f}"
            )
            if drop > threshold:
                failures.append(
                    f"{key} dropped by {drop:.4f} (baseline={baseline_val:.4f}, "
                    f"current={current_val:.4f}, threshold={threshold:.4f})"
                )

        assert not failures, "Recall regression: " + "; ".join(failures)
