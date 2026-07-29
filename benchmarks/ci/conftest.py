"""Pytest configuration for the CI benchmark suite.

Adds custom CLI flags so the harness can be invoked as a standard pytest
run with configurable output paths and regression thresholds, and writes
the results artifact at session end.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("benchmark", "CI benchmark options")
    group.addoption(
        "--benchmark-output",
        default="benchmark_results.json",
        help="Path to write the JSON results file (default: benchmark_results.json)",
    )
    group.addoption(
        "--baseline-file",
        default=None,
        help="Path to baseline JSON for regression comparison. "
        "If not provided, regression checks are skipped.",
    )
    group.addoption(
        "--latency-threshold",
        type=float,
        default=0.20,
        help="Max allowed fractional increase in p95 latency vs baseline "
        "(default: 0.20 = 20%%)",
    )
    group.addoption(
        "--recall-threshold",
        type=float,
        default=0.05,
        help="Max allowed absolute decrease in recall@5 and recall@10 vs "
        "baseline (default: 0.05 = 5 percentage points)",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Serialize benchmark results after the run.

    Writing here (rather than in a test that must be collected last) means
    the artifact is emitted regardless of test ordering, ``-x``/``--maxfail``
    early exits, or a failing regression guard — CI's ``if: always()``
    artifact upload always has real data to capture.
    """
    config = session.config
    if config.option.collectonly:
        return
    results = getattr(config, "_benchmark_results", None)
    if results is None:
        # No measurement fixture was ever instantiated (e.g. credentials
        # missing and everything skipped). Still emit a stub so the artifact
        # documents that nothing was measured instead of silently vanishing.
        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "no benchmark measurements ran in this session",
            "latency_ms": {},
            "recall": {},
        }
    output_path = Path(config.getoption("--benchmark-output"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark results written to: {output_path}")
