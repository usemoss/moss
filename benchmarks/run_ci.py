"""Record the existing Moss workload using local indexing, with truthful exits."""

import argparse
import asyncio
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from dotenv import dotenv_values

import bench_moss
from competitor_agreement import load_reference, score_agreement, sentence_template
from corpus import get_queries, load_fixed_documents
from latency_guard import check_latency, latency_context, load_baseline
from local_moss import run_local_async


ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def redact(value, secrets):
    """Redact before JSON escaping, including nested error/configuration strings."""
    if isinstance(value, str):
        for secret in sorted({secret for secret in secrets if secret}, key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value


def write_record(path, record, secrets):
    """Replace the result atomically so an interrupted write is not valid JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(redact(record, secrets), indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
            prefix=".benchmark-", suffix=".tmp",
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def git_output(*args):
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def package_version(distribution):
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def provenance():
    status = git_output("status", "--porcelain")
    return {
        "repository_sha": git_output("rev-parse", "HEAD"),
        "working_tree_dirty": bool(status) if status is not None else None,
        "runtime_under_test": "installed-release",
        "sdk": {"version": package_version("moss")},
        "native_core": {"version": package_version("inferedge-moss-core")},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "runner_label": os.getenv("MOSS_BENCHMARK_RUNNER"),
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
    }


def measurement_record(measurement):
    raw = measurement.latencies_ms
    expected = bench_moss.QUERY_ROUNDS * len(get_queries())
    if len(raw) != expected or measurement.result.count != expected:
        raise ValueError(f"Expected {expected} measured samples, got {len(raw)}")
    if not all(isinstance(value, (int, float)) and math.isfinite(value) and value > 0 for value in raw):
        raise ValueError("Measured durations must be finite positive milliseconds")
    first = measurement.first_query_ms
    if not isinstance(first, (int, float)) or not math.isfinite(first) or first <= 0:
        raise ValueError("First-query duration must be finite positive milliseconds")
    stats = measurement.result
    return {
        "measured_query_count": stats.count,
        "first_query_after_setup_ms": measurement.first_query_ms,
        "raw_latencies_ms": raw,
        "latency_ms": {
            "p50": stats.p50, "p95": stats.p95, "p99": stats.p99,
            "mean": stats.mean, "stdev": stats.stdev,
        },
        "first_measured_round_rankings": measurement.rankings,
    }


def prepare_competitor_reference(path):
    documents, dataset_sha = load_fixed_documents()
    reference = load_reference(path, dataset_sha, get_queries())
    templates = {row["id"]: sentence_template(row["text"]) for row in documents}
    reference_ids = {
        doc_id
        for rankings in reference["rankings"].values()
        for hits in rankings.values()
        for doc_id in hits
    }
    if not reference_ids <= templates.keys():
        raise ValueError("Competitor reference contains IDs absent from the benchmark corpus")
    return reference, templates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".benchmark-results/result.json")
    parser.add_argument("--env-file", type=Path, help="Explicit local credentials file; never discovered automatically")
    parser.add_argument("--baseline", type=Path, help="Compare p95 against an approved baseline JSON file")
    parser.add_argument("--competitor-reference", type=Path, help="Report agreement with saved competitor rankings")
    args = parser.parse_args(argv)
    for option, path in (("--baseline", args.baseline), ("--competitor-reference", args.competitor_reference)):
        if path and args.output.resolve() == path.resolve():
            parser.error(f"--output and {option} must be different files")
    configuration = dict(dotenv_values(args.env_file)) if args.env_file else {}
    configuration.update(os.environ)
    project_id = configuration.get("MOSS_PROJECT_ID")
    project_key = configuration.get("MOSS_PROJECT_KEY")
    secrets = (project_id, project_key)
    record = {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": utc_now(),
        "benchmark_mode": "local-session-fresh",
        "quality": {"status": "not_evaluated" if args.competitor_reference else "not_configured", "recall": None},
        "regression": {"status": "not_evaluated" if args.baseline else "not_configured", "baseline": None},
        "timing_scope": "Local query embedding plus retrieval; setup, validation and warmups excluded",
    }
    try:
        record["provenance"] = provenance()
        baseline = None
        if args.baseline:
            record["regression"]["status"] = "invalid_baseline"
            baseline = load_baseline(args.baseline)
            record["regression"] = {"status": "not_evaluated", "baseline": baseline["baseline_commit"]}
        reference = None
        if args.competitor_reference:
            record["quality"]["status"] = "invalid_reference"
            reference, templates = prepare_competitor_reference(args.competitor_reference)
            record["quality"]["status"] = "not_evaluated"
        write_record(args.output, record, secrets)
        if not project_id or not project_key:
            raise ValueError("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY; no .env file is loaded automatically")
        run = asyncio.run(run_local_async(project_id, project_key))
        measured = measurement_record(run.measurement)
        record.update(measured)
        record["configuration"] = run.configuration
        record["setup"] = run.setup
        context = latency_context(run.configuration, record["provenance"])
        record["latency_context"] = context
        if reference is not None:
            record["quality"]["status"] = "invalid_reference"
            if run.configuration["dataset_sha256"] != reference["dataset_sha256"]:
                raise ValueError("Competitor agreement requires the measured and reference corpus to match")
            agreement = score_agreement(reference, run.measurement.rankings, templates)
            record["quality"].update(status=agreement["status"], competitor_agreement=agreement)
        if baseline is not None:
            result = check_latency(baseline, context, measured["latency_ms"]["p95"])
            record["regression"] = result
            if result["status"] != "passed":
                raise ValueError(result["reason"])
        record["status"] = "success"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        print(redact(f"Benchmark failed: {type(exc).__name__}: {exc}", secrets), file=sys.stderr)
    finally:
        record["completed_at_utc"] = utc_now()
        write_record(args.output, record, secrets)
    print(f"{record['status']}: result saved to {args.output}")
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
