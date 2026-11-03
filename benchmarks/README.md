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

The first CI integration stage runs this workload through a local
`SessionIndex`. It shares the original benchmark's query loop, `Timer`, and
percentile calculation. The existing cloud-loaded benchmark and competitor
commands above remain available; their timings are a separate measurement
mode and must not be treated as interchangeable baselines.

From the repository root, with Python 3.12 and your Moss credentials:

```bash
python -m pip install -r benchmarks/requirements-ci.txt
python benchmarks/run_ci.py --env-file benchmarks/.env --output .benchmark-results/local.json
```

The explicit credentials file needs `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`.
Alternatively, supply those environment variables and omit `--env-file`.
The CI entry point never discovers `.env` files automatically. Credentials
are not included in the result; configured project credentials are redacted
from recorded errors. Do not commit your `.env` file.

The local mode checks the full file's SHA-256, record count, IDs, and text,
then indexes all 100,000 documents in sequential batches. It disables cloud
index loading and never creates, deletes, or pushes a cloud index. A fresh
document index is built for every run; authentication, built-in model
authorization/download, and usage reporting still use Moss services. Local
execution does not establish zero cost: review your account's session usage
and [current pricing](https://docs.moss.dev/docs/pricing) before enabling it.

Only the awaited text-query calls are timed, including query embedding and
retrieval. Index construction, result validation, the first query after
setup, and 45 warmup queries are excluded from the 750 measured samples.
Returned hits must be five unique IDs from the corpus. This is a data/harness
check, not a relevance or recall score. The first measured round's rankings
are retained; subsequent ranking stability is not evaluated.

JSON records raw timings, p50/p95/p99/mean/stdev, setup durations, actual
configuration and input fingerprints, repository revision/source hashes,
installed SDK/core versions and file fingerprints, and host/Python details.
The runtime under test is the pinned installed release, **not edits to the
release-synced SDK source snapshots**. The exact model artifact is not exposed
by the public session property, so the record reports it as unknown rather
than treating a model alias as an immutable version.

Failed measurements exit nonzero and leave failure JSON. Successful timing
records explicitly mark quality and regression checks `not_configured`.
Do not use `run_all.py` as a CI exit signal: its aggregate exception handling
can finish with a successful exit after a backend fails.

### GitHub Actions setup

`.github/workflows/benchmark.yml` runs offline tests on pull requests and
main-branch pushes. Maintainers can enable live main-branch measurements by
setting repository variable `MOSS_BENCHMARK_ENABLED` to `true` and repository
secrets `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`. Review the account budget
before opting in. Manual runs must also target `main`; no PR code receives
Moss secrets. Missing credentials fail an enabled measurement instead of
silently skipping it. Disabled/PR runs state that live latency was not measured.

Live jobs use Ubuntu 24.04/Python 3.12, the pinned minimal runtime, and a
60-minute timeout. A local Mac run established feasibility, not Linux timing
or a CI baseline. Each live run uploads only its result JSON, including
failures, as a temporary 90-day workflow artifact with a unique run name.

**Generated indexes, snapshots, embeddings, model caches, device identity,
credentials, and private run outputs stay out of the PR.** No document-index
cache or binary artifact upload is configured. Automatic index reuse needs
an authoritative model identity, data/build/runtime compatibility, and
artifact validation before it can be trusted.

This is partial progress toward #435. It does not yet implement recall, a
regression threshold/baseline, or durable published history. Workflow artifacts
are temporary and do not replace the commit/run history still to be designed.

### Offline checks

```bash
python -m unittest discover -s benchmarks/tests -v
python -m compileall -q benchmarks
```

The tests use controlled SDK/session fakes and no project credentials or
service calls. They exercise the actual fixed-data loader, local builder,
shared timing loop, and result/exit behavior. They verify harness contracts,
not retrieval quality or performance.
