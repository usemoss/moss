# Search Benchmark Tests (JS User-Facing SDK)

This folder contains the **search benchmark runner** for the JavaScript user-facing SDK:

- `test/search.test.ts` — creates indices from datasets in `test-dataset/`, runs search queries, computes metrics, and cleans up indices.

Dataset preparation docs live in `test-dataset/README.md`.

---

## Benchmark pipeline (high-level)

```text
test-dataset/ (prepared data)
  ├─ corpus.jsonl
  ├─ queries.jsonl
  └─ qrels.tsv
           │
           ▼
test/search.test.ts
  ├─ creates one index per dataset (name includes SDK version)
  ├─ loads qrels/queries (writes qrels_cache.json for speed)
  ├─ runs client.query() and scores results vs qrels
  ├─ prints metrics (HitRate, MRR, NDCG, latency)
  └─ deletes all indices it created
```

**Important:** this runner uses the MOSS Cloud API and will create/delete indices in your project.

---

## Metrics (what the table means)

The benchmark evaluates search quality using four key metrics:

### 1. Hit Rate

**Definition:** Percentage of queries where at least one relevant document appears in the top-k results.

**Interpretation:**

- Range: 0.0 to 1.0 (0% to 100%)
- Higher is better
- Measures basic retrieval success

### 2. MRR (Mean Reciprocal Rank)

**Definition:** Average of the reciprocal rank of the first relevant document found.

**How it works:**

- For each query, finds the rank of the **first** relevant document
- If found at rank `r`, contributes `1/r` to the sum
- If not found, contributes 0
- Only the first relevant document counts, even if multiple relevant documents appear in results

**Interpretation:**

- Range: 0.0 to 1.0
- Higher is better
- Penalizes relevant documents that appear lower in results
- Example: MRR of 0.5 means the first relevant doc appears at rank 2 on average

### 3. NDCG (Normalized Discounted Cumulative Gain)

**Definition:** Ranking quality metric that considers both relevance scores and position.

**How it works:**

- Calculates DCG (Discounted Cumulative Gain) by summing relevance scores with position discounts
- Normalizes by the ideal DCG (perfect ranking)
- Higher relevance scores and higher positions contribute more

**Interpretation:**

- Range: 0.0 (worst) to 1.0 (perfect ranking)
- Higher is better
- Most comprehensive metric, considers full ranking quality

### 4. Latency Metrics

- **Average Latency:** Mean response time across all queries (milliseconds)
- **P95 Latency:** 95th percentile response time (milliseconds) — 95% of queries complete faster than this value

---

## Running locally

### 1) Set credentials

You can export environment variables, or create a `.env` file (dotenv is loaded by `test/constants.ts`).

Example (export):

```bash
export MOSS_TEST_PROJECT_ID=...
export MOSS_TEST_PROJECT_KEY=...
```

### 2) Run the benchmark

Because the script imports `@moss-dev/moss` via the package’s `exports`, build once before running:

```bash
cd sdks/javascript/sdk
npm install
npm run build
npx tsx test/search.test.ts
```

### Dataset path resolution

The runner locates `test-dataset/` in this order:

1. `MOSS_BENCH_DATASET_PATH` (if set)
2. `<cwd>/test-dataset` (if it exists)
3. relative to the script location (`../../../test-dataset`)

If you run it from unusual working directories (or in your own automation), set:

```bash
export MOSS_BENCH_DATASET_PATH="/absolute/path/to/repo/test-dataset"
```

---

## CI: GitHub Actions matrix (version bench)

The workflow file is:

- `.github/workflows/js-ufs-search-test.yml`

This workflow benchmarks **multiple JS SDK versions** using a **matrix**.

### How “version running” works in CI

The workflow builds a matrix from a JSON array of versions:

- If the matrix value is a semver tag (e.g. `"1.0.0-beta.2"`), it installs `@moss-dev/moss@<that version>` from npm.
- If the matrix value is `"source"`, it:
  - builds `sdks/javascript/sdk` from this repo
  - packs it into a tarball (`npm pack`)
  - installs that tarball into a neutral runner environment

To avoid module resolution quirks, the workflow copies the benchmark files into a “neutral” folder:

- `bench-runner/js-ufs-version/`

and then runs:

- `npx tsx bench-runner/js-ufs-version/search.test.ts`

### Required secrets

The workflow expects these repository secrets:

- `MOSS_TEST_PROJECT_ID`
- `MOSS_TEST_PROJECT_KEY`

### How to run the workflow

- **From GitHub UI**: Actions → “JS User-Facing SDK Search Benchmark Tests” → “Run workflow”
  - `versions` input must be a JSON array, e.g. `["1.0.0-beta.2","source"]`
  - `node_version` defaults to `20`

- **From CLI (`gh`)**:

```bash
gh workflow run js-ufs-search-test.yml \
  -f versions='["1.0.0-beta.2","source"]' \
  -f node_version='20'
```
