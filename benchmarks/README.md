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

A failed run exits nonzero and writes a report with project credentials
redacted from errors. Recall and regression checks are marked `not_configured`.

### GitHub Actions setup

`.github/workflows/benchmark.yml` runs offline tests on pull requests to `main`
and pushes to `main`. To enable live measurements on pushes and manual runs
on `main`, set `MOSS_BENCHMARK_ENABLED` to `true` and add `MOSS_PROJECT_ID` and
`MOSS_PROJECT_KEY` as repository secrets.

GitHub Actions uploads the JSON report if the runner writes one, including
after a failed measurement, and keeps it for 90 days. Keep generated indexes
and model caches local. Recall, regression thresholds, and durable results
history remain open for #435.

### Offline checks

```bash
python -m unittest discover -s benchmarks/tests -v
python -m compileall -q benchmarks
```

These tests check index setup, timing, and reporting with a fake Moss session
and run without project credentials.
