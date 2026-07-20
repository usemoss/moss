"""Pytest configuration for the CI benchmark suite.

Adds custom CLI flags so the harness can be invoked as a standard pytest
run with configurable output paths and regression thresholds.
"""

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
        help="Max allowed absolute decrease in recall@k vs baseline "
        "(default: 0.05 = 5 percentage points)",
    )
