# Benchmark: Moss vs Pinecone vs Qdrant vs ChromaDB

Reproducible end-to-end latency benchmarks for semantic search.
**All measurements include embedding generation time** — the full cost
a developer actually pays per query.

## What's being measured

Each benchmark times the complete query cycle:

| System | What happens per query |
|--------|----------------------|
| **Moss** | `client.query(index_name, "text")` — embedding + search in one call |
| **Pinecone** | Call embedding API → send vector to Pinecone cloud → get results |
| **Qdrant** | Call embedding API → send vector to Qdrant Cloud → get results |
| **ChromaDB** | Call embedding API → search local Chroma collection → get results |

Moss bundles a built-in embedding model. Competitors require an external
embedding service (OpenAI, self-hosted, etc.).

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in credentials
cp .env.example .env
# Edit .env with your API keys

# 3. Run all benchmarks
python run_all.py

# Or run individually
python run_all.py moss
python run_all.py qdrant chroma
```

### Required credentials

| Benchmark | What you need |
|-----------|--------------|
| Moss | `MOSS_PROJECT_ID` + `MOSS_PROJECT_KEY` |
| Pinecone | `PINECONE_API_KEY` |
| Qdrant | `QDRANT_URL` + `QDRANT_API_KEY` |
| ChromaDB | Nothing (runs locally in-memory) |
| Embedding | `OPENAI_API_KEY` or a custom endpoint URL |

### Embedding provider

Competitors need an embedding service. Two options:

**Option A: OpenAI (default)**
Set `OPENAI_API_KEY` in `.env`. Uses `text-embedding-3-small` (1536 dims).
This is the most common production setup.

**Option B: Self-hosted on [Modal](https://modal.com/docs/examples/text_embeddings_inference)**
Deploy the embedding server:
```bash
pip install modal
modal deploy embedding_server/modal_app.py
```
Then set in `.env`:
```
EMBEDDING_PROVIDER=custom
EMBEDDING_ENDPOINT=https://your-app--embedding-server-model-embed.modal.run
EMBEDDING_DIMENSION=768
```

## Test data

`bench_100k_docs.json` contains 100,000 synthetic text records made from
variations of 20 computer-science/AI sentences. It contains IDs and text,
not relevance labels. The local CI mode below reads and validates this file.
The original competitor runners obtain documents from the configured cloud
Moss index, so their dataset depends on that index's contents.

## Benchmark parameters

- **Documents**: 100,000 synthetic text records for the local mode
- **Queries**: 15 diverse search queries
- **Warmup**: 3 rounds (excluded from measurements)
- **Measured**: 50 rounds x 15 queries = 750 measurements per system
- **top_k**: 5

## Local indexing and CI results

This mode uses the existing query loop with a fresh local index built from
all 100,000 documents. Compare runs within the same index mode.

From the repository root, with Python 3.12 and your Moss credentials:

```bash
python -m pip install -r benchmarks/requirements-ci.txt
python benchmarks/run_ci.py --env-file benchmarks/.env --output .benchmark-results/local.json
```

Supply `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` in the environment or in the
file passed to `--env-file`. Keep that file private. The local index build
still uses Moss for authentication, model access, and usage reporting. Review
your account's session usage before enabling live runs. [Moss pricing](https://docs.moss.dev/docs/pricing)

The 750 timing samples cover query embedding and retrieval. The report
records setup and first-query time separately and excludes warmups. It saves
p50/p95/p99, raw samples, and the first measured round's result IDs. Each
query must return five unique IDs from the dataset. The report identifies
the commit, local edits flag, dataset, query set, host, and installed SDK/core
versions. The benchmark runs against the pinned SDK release installed from
PyPI. The report records the model alias and marks its exact artifact unknown.

Argument parsing errors exit with code 2 before report creation. Once a run
starts, runtime failures exit with code 1 and write failure JSON when output
file I/O permits. Project credentials are redacted from recorded errors.
`quality.recall` is `null`. The p95 regression check requires a configured baseline.

### GitHub Actions setup

`.github/workflows/benchmark.yml` runs offline tests on pull requests to `main`
and pushes to `main`. To enable live measurements on pushes and manual runs
on `main`, set `MOSS_BENCHMARK_ENABLED` to `true` and add `MOSS_PROJECT_ID` and
`MOSS_PROJECT_KEY` as repository secrets.

GitHub Actions uploads the JSON report if the runner writes one, including
after a failed measurement, and keeps it for 90 days. Keep generated indexes
and model caches local. Recall and durable results history remain open for #435.

### Optional p95 latency guard

By default, live runs report latency only. To enable the guard for live
`main` runs, track `benchmarks/latency-baseline.json` and set
`MOSS_BENCHMARK_LATENCY_GUARD_ENABLED` to `true`. Pull requests run the offline
tests. The guard detects slowdowns after changes land on `main`.

The baseline JSON has four fields.

- `baseline_commit` is the full SHA of the known-good commit.
- `p95_ms` is the median of that commit's per-run p95 measurements in milliseconds.
- `max_slowdown_pct` is the positive percent increase allowed over the baseline.
- `compatibility` is the `latency_context` object copied from a successful run
  with the same workload and runner. It matches the workload, runner class, OS,
  architecture, CPU count, and Python major/minor version. SDK and core versions
  may change because their performance is part of what the guard measures.

Collect 8–10 independent runs of the same known-good commit on the same CI
runner class, spread across hosts and times. Set the margin above the largest
observed increase over the median, with some headroom for run-to-run noise.
Verify the margin on additional runs of the same commit and keep it below the
smallest slowdown that matters to the project. For example, a hypothetical
20 ms baseline with a 15% margin allows up to 23 ms. Keep the baseline fixed
until it can be reviewed and deliberately replaced. This change ships without
a baseline collected on the live runner.

To check a baseline directly, pass `--baseline PATH` to `run_ci.py`, using
the same workload and runner context recorded in the file. A missing,
malformed, or incompatible configured baseline fails as a configuration
error. A p95 above the limit fails as a regression and preserves the measured
latencies in the JSON report.

### Optional competitor agreement

Capture Pinecone, Qdrant, and Chroma's top five results on the same checked-in
corpus and queries as Moss. Each engine receives text and handles embedding.
Qdrant uses local FastEmbed and Chroma uses its default local embedding model.
Pinecone requires an existing, dedicated dense cosine index created with
`create_for_model` for integrated embedding. The collector uses a temporary
namespace and cleans it up on exit.

```bash
python -m pip install 'pinecone>=10,<11' 'qdrant-client[fastembed]>=1.14.2,<2' 'chromadb>=1,<2' 'python-dotenv>=1,<2'
python benchmarks/capture_competitor_rankings.py --env-file benchmarks/.env --output .benchmark-results/competitor-reference.json
```

Supply `PINECONE_API_KEY` and `PINECONE_INDEX_NAME` in the environment or
explicit credentials file. On first use, the local clients download their
models. Review Pinecone usage before capture. The full capture sends corpus
and query text to Pinecone and keeps two local indexes in memory.

Run `python benchmarks/run_ci.py --competitor-reference PATH` with a saved
reference. For live CI, track the reviewed file as
`benchmarks/competitor-reference.json` and set
`MOSS_BENCHMARK_COMPETITOR_AGREEMENT_ENABLED` to `true`. CI reads the saved
rankings with no competitor SDKs, credentials, or service calls.

A template gets one vote per competitor that returns it. For each query,
the score is the fraction of templates with two or more votes that Moss
finds in its top five. Queries without any agreement are left unscored. The
report includes the per-query scores, their mean, how many were scored, and
the model used by each engine. The score is report-only. An invalid or
incompatible configured reference fails as a configuration error. Relevance
recall remains unconfigured.

### Offline checks

```bash
python -m unittest discover -s benchmarks/tests -v
python -m compileall -q benchmarks
```

These tests check index setup, timing, and reporting with a fake Moss session
and run without project credentials.
