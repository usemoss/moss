# CI Benchmark Suite — Latency & Recall Regression Guard

Automated benchmark harness that runs on every push/PR to `main` and catches
performance regressions before they ship.

## What it measures

| Metric | Description |
|--------|-------------|
| **P50 / P95 / P99 latency** | End-to-end query latency (embedding + search) in ms |
| **Mean / Stdev** | Average and standard deviation of latency |
| **Recall@5** | Fraction of ground-truth top-5 docs returned in top 5 |
| **Recall@10** | Fraction of ground-truth top-10 docs returned in top 10 |

All measurements use the Moss built-in embedding model (`moss-minilm`) with a
1,000-document subset of the benchmark corpus for CI speed.

## Quick start

### Prerequisites

Set `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` in your environment (or in a
`.env` file).

### Run locally

```bash
# Install dependencies
pip install -r benchmarks/ci/requirements.txt

# Run the full suite
pytest benchmarks/ci/ -v \
  --benchmark-output=benchmark_results.json \
  --baseline-file=benchmarks/ci/baseline.json

# Skip regression checks (no baseline comparison)
pytest benchmarks/ci/ -v --benchmark-output=benchmark_results.json
```

### Regenerate ground truth

Run this when the index data or model changes:

```bash
python benchmarks/ci/generate_ground_truth.py
```

This queries Moss with `top_k=50` for each benchmark query and writes the
expected document IDs to `ground_truth.json`. Commit the updated file.

## How regression detection works

The harness compares the current run's metrics against `baseline.json`:

- **Latency**: Fails if P95 increases by more than the threshold (default 20%)
- **Recall**: Fails if Recall@5 drops by more than the threshold (default 5pp)

Thresholds are configurable via CLI flags:

```bash
pytest benchmarks/ci/ -v \
  --latency-threshold=0.15 \  # 15% max P95 regression
  --recall-threshold=0.03     # 3pp max recall drop
```

## Updating the baseline

After a legitimate performance change (e.g., model upgrade, index config
change), update the baseline:

1. **Via GitHub Actions**: Trigger the `Benchmark` workflow manually with
   `update_baseline=true`
2. **Manually**: Copy a CI run's `benchmark_results.json` artifact to
   `benchmarks/ci/baseline.json` and commit

## CI integration

The benchmark runs as a GitHub Actions job (`.github/workflows/benchmark.yml`).
Results are uploaded as artifacts named `benchmark-results-<sha>` and are
available for download from the Actions tab.

## File overview

| File | Purpose |
|------|---------|
| `test_bench_ci_moss.py` | Main test module (latency, recall, regression guard) |
| `conftest.py` | Pytest CLI flags |
| `generate_ground_truth.py` | One-time ground truth generator |
| `ground_truth.json` | Pre-computed expected results per query |
| `baseline.json` | Performance baseline for regression checks |
| `requirements.txt` | Python dependencies |
