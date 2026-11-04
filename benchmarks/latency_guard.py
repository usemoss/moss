"""Compare the p95 of a complete benchmark run against an approved baseline."""

from decimal import Decimal
import json
import math
import re


WORKLOAD_FIELDS = (
    "mode", "setup_mode", "dataset_sha256", "query_sha256", "model_id",
    "model_artifact_id", "doc_count", "query_count", "top_k", "alpha",
    "warmup_rounds", "query_rounds",
)
RUNNER_FIELDS = ("label", "os", "machine", "cpu_count", "python")


def latency_context(configuration, provenance):
    # SDK and core versions are recorded separately. Upgrades are candidates
    # for comparison, whereas the workload and runner class must match.
    return {
        "workload": {field: configuration[field] for field in WORKLOAD_FIELDS},
        "runner": {
            "label": provenance["runner_label"],
            "os": provenance["system"],
            "machine": provenance["machine"],
            "cpu_count": provenance["cpu_count"],
            "python": ".".join(provenance["python"].split(".")[:2]),
        },
    }


def load_baseline(path):
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(baseline, dict):
        raise ValueError("Latency baseline must be a JSON object")
    commit = baseline.get("baseline_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Latency baseline requires a full baseline_commit SHA")
    for field in ("p95_ms", "max_slowdown_pct"):
        value = baseline.get(field)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Latency baseline {field} must be a finite positive number")

    context = baseline.get("compatibility")
    if not isinstance(context, dict) or set(context) != {"workload", "runner"}:
        raise ValueError("Latency baseline compatibility must copy the report's latency_context")
    for section, fields in (("workload", WORKLOAD_FIELDS), ("runner", RUNNER_FIELDS)):
        if not isinstance(context[section], dict) or set(context[section]) != set(fields):
            raise ValueError(f"Latency baseline compatibility.{section} has unexpected fields")

    # Compute the configured decimal limit before rounding it to a timing float.
    p95 = Decimal(str(baseline["p95_ms"]))
    allowance = Decimal(str(baseline["max_slowdown_pct"])) / 100
    baseline["limit_ms"] = float(p95 * (1 + allowance))
    if not math.isfinite(baseline["limit_ms"]):
        raise ValueError("Latency baseline produces a nonfinite limit")
    return baseline


def check_latency(baseline, context, p95_ms):
    result = {
        "status": "passed",
        "baseline": baseline["baseline_commit"],
        "baseline_p95_ms": baseline["p95_ms"],
        "max_slowdown_pct": baseline["max_slowdown_pct"],
        "limit_p95_ms": baseline["limit_ms"],
        "observed_p95_ms": p95_ms,
    }
    differences = [
        f"{section}.{field}"
        for section, expected in baseline["compatibility"].items()
        for field, value in expected.items()
        if context[section][field] != value
    ]
    if differences:
        result["status"] = "incompatible_baseline"
        result["reason"] = "Latency baseline differs in " + ", ".join(differences)
    elif p95_ms > baseline["limit_ms"]:
        result["status"] = "regressed"
        result["reason"] = f"P95 latency {p95_ms:.3f} ms exceeded the {baseline['limit_ms']:.3f} ms limit"
    return result
