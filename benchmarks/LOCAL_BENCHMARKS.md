# Local benchmarks: Moss ingest memory and on-device latency

These benchmarks run everything in-process on one machine: Moss sessions, ChromaDB, LanceDB and Qdrant
(local mode), with on-device MiniLM embeddings. The cloud benchmarks in [README.md](README.md) are separate.

What they show (numbers in [benchmark-reference-results.md](benchmark-reference-results.md)):

- **Moss built-in ingest memory scales with the docs (tokens) in each `add_docs` call.** 1,000 paper chunks
  in one call peak at 14.5 GB; the same chunks in calls of 100 peak at 2.2 GB and take the same time. At 64k
  short docs in one call, the process peaks at 69.8 GB. The custom-embedding path at 10k docs stays near 1.1 GB.
- **End-to-end query latency (embed + search) at 10k short docs:** Moss p50 1.33 ms; Chroma 4.45; LanceDB 5.55
  (HNSW) and 6.63 (flat); Qdrant 7.09. Most of the gap is fixed-length padding in the competitors' query
  embedders. Chroma with unpadded queries reaches 1.50 ms.

## Prerequisites

| Need | Details |
|---|---|
| macOS | Tested on Apple Silicon (M5 Max, 128 GB). `watchdog.sh` reads macOS memory-pressure levels (`sysctl`), so Linux is not supported as-is. |
| RAM | The smoke test peaks at about 4 GB and the competitor runs at about 2.5 GB. The headline Moss memory runs peak at 11–22 GB; the ramps stop themselves when the projected next peak exceeds 75% of RAM. |
| [uv](https://docs.astral.sh/uv/) | Creates `.venv` from `uv.lock` and downloads Python 3.12.13 if needed. |
| Moss project | A project ID and key from the [Moss portal](https://portal.usemoss.dev). Needed only for runs that create Moss sessions. |
| Network | Model downloads (first run), arXiv PDFs, and Moss Cloud authentication for Moss sessions. |
| Ollama (optional) | Only for `doc_chunk_eval`, with `ollama pull qwen3-embedding:4b-q8_0`. The loaded model uses about 11 GB. |

## Quick start

All commands run from `benchmarks/`.

```bash
cd benchmarks
./run_local.sh setup          # .venv with exact pins from uv.lock + the fastembed MiniLM model
./run_local.sh fetch-arxiv    # 12 arXiv PDFs into data/arxiv/, sha256-verified
export MOSS_ENV_FILE=/path/to/.env   # file containing MOSS_PROJECT_ID=... and MOSS_PROJECT_KEY=...
./run_local.sh smoke          # every benchmark at small sizes, about 5 minutes, peak about 4 GB
./run_local.sh list           # every benchmark, its arguments, credentials and cost
```

Instead of `MOSS_ENV_FILE`, you can export `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` directly. Without
either, the smoke test skips the Moss runs and runs everything else.

`./run_local.sh run <name> [args]` runs one benchmark (the script name without `.py`) under
`watchdog.sh` and writes `results/<name>-<args>.log`. The watchdog kills the run if macOS memory pressure
leaves "normal", if its RSS passes 85% of RAM, or after 20 minutes. To stop any run by hand:

```bash
pkill -9 -f 'benchmarks/.venv/bin/python'
```

## Reproduce the memory issue

```bash
./run_local.sh memory-repro
```

This asks for confirmation, builds the paper corpus if needed, then runs `moss_mem 100` (about 2.2 GB peak)
and `moss_mem 1000` (about 22 GB peak, including the re-ingest). Each run appends one JSON line to
`results/docchunk/moss_mem.jsonl`: RSS in MB after session create, ingest, deleting every doc, re-ingesting
the same docs and dropping the session, plus ingest times. Compare the `peak after ingest` values.

## Benchmarks

Run them one at a time; parallel runs distort both memory and latency. Times and peaks below are from the
reference machine. "Creds" means the run creates Moss sessions, which need credentials and are metered.

| Name and args | Measures | Creds | Peak RSS / time | Output in `results/` |
|---|---|---|---|---|
| `bench_local lancedb\|lancedb-hnsw\|chroma\|chroma-unpadded\|qdrant` | 10k short docs: end-to-end and search-only query latency, fastembed MiniLM | no | ~2.5 GB, 30–45 s | `<db>.txt/.json` |
| `bench_local moss` | The same with Moss's built-in `moss-minilm`; 10k docs in one `add_docs` call | yes | **~11 GB**, ~30 s | `moss.txt/.json` |
| `bench_embed` | Query-embedding latency, fastembed vs Moss native, plus their cosine | no | ~0.5 GB, ~15 s | `embed-*.txt/.json` |
| `bench_embed_tuning` | fastembed threads and CoreML, raw ONNX Runtime (tokenize vs inference), int8 | no | ~1.5 GB, ~40 s | `tune-*.txt/.json` |
| `doc_chunk_builtin prep` | Builds the corpora: first 1,000 paper chunks and first 1,000 short docs | no | small, seconds | `docchunk/builtin-*-docs.json` |
| `batch_padding` | ONNX ingest throughput by batching and padding strategy, vector identity | no | ~1 GB, ~30 s | `batch_padding.txt` |
| `doc_chunk_builtin run <system> paper\|small <n>` | Built-in embedders on n docs; system = `moss`, `chroma` (default embedder), `chroma-reuse`, `chroma-unpadded` | moss only | moss paper 1000: **14.5 GB** | `docbuiltin-<system>-<corpus>-<n>.*` |
| `doc_chunk_builtin ramp [max_n]` | The `run` steps from 125 to 1,000 paper chunks, then 1,000 short docs, for moss and chroma | yes | up to **14.5 GB**, several minutes | the same, plus `.log` per step |
| `moss_mem <docs_per_call> [n_docs]` | Memory by docs per `add_docs` call; delete, re-ingest, session drop | yes | 1000: **~22 GB**; 100: ~2.2 GB; 1: ~0.5 GB but slowest; 40–70 s | `docchunk/moss_mem.jsonl` |
| `moss_scale <n_docs> [docs_per_call]` | One built-in Moss session at n short docs: RSS per stage, ingest time, latency. Default: all docs in one `add_docs` call | yes | one call: ~1.1 MB per doc; 100 per call: under 1 GB at 8k | `moss-scale-<n>[-per<k>].*` |
| `moss_ramp [max_docs]` | `moss_scale` at 1k, 2k, … 100k; halts when the projected next peak exceeds 75% of RAM | yes | **reached 69.8 GB at 64k**, ~5 min | `moss-scale-<n>.*`, `moss_ramp.log` |
| `moss_persist build` | Custom-embedding ingest (embed vs index time), search-only latency, `save_to_disk` | yes | ~1.1 GB, ~20 s | `moss-search-only.*`, `persist_state.json`, `.moss-sessions/` |
| `moss_persist restore` / `restore-fake` | Restore in a new process; with fake credentials, shows that the native session rejects them | restore only | small | log only |
| `doc_chunk_eval prep`, `query-embed`, `run moss\|chroma paper\|small` | Paper chunks vs short docs with precomputed qwen3 vectors; Ollama throughput and model memory | moss only | **~11 GB** in the Ollama process | `docchunk/*` |

Order dependencies:

- `fetch-arxiv`, then `doc_chunk_builtin prep`, before `batch_padding`, `moss_mem` and `doc_chunk_builtin run/ramp`.
- `moss_persist build` before `restore` and `restore-fake`.
- `doc_chunk_eval prep` (needs Ollama running) before its other modes.

Environment overrides: `BENCH_DOCS` changes the 10k doc count of `bench_local` and `moss_persist`;
`BENCH_RESULTS` changes the output directory (the smoke test uses `results/smoke/`).

## The paper corpus

`arxiv.sha256` lists the 12 PDFs in corpus order; `fetch-arxiv` downloads each from
`https://arxiv.org/pdf/<id>`, 3 seconds apart, and verifies the hashes. The PDFs are not committed (their
licenses vary). `doc_chunk_eval` uses the first two; `doc_chunk_builtin` chunks all 12 in order (under 256
tokens, 32-token overlap) and keeps the first 1,000 chunks, which end in the tenth PDF. With `pypdf` 6.18.1,
`prep` must print:

```
paper: 1000 docs from 10 sources; tokens incl. specials min/median/max 6/222/255, total 192038
```

A different `pypdf` version can change text extraction and so the chunks. If a hash fails, delete that file
from `data/arxiv/` and rerun `fetch-arxiv`.

## Reading the outputs

- `<name>.txt`: a header with the machine, the in-process peak RSS (`ru_maxrss`) and versions, then mean,
  stdev, P50, P95 and P99 in ms for each series. `<name>.json` holds the raw per-query latencies.
- `<name>-<args>.log`: the full console output. Its last line comes from the watchdog, with the peak RSS it
  sampled every 0.2 s (`peak_rss_mb`) and the highest memory-pressure level (1 is normal).
- End-to-end latency includes the query embedding; search-only uses a precomputed query vector.
- Moss and the competitors use the same MiniLM-L6-v2 weights (cosine 1.000000 between their vectors), so the
  latency differences come from the runtimes, not the models.

To compare with [benchmark-reference-results.md](benchmark-reference-results.md), run the same command with
the default sizes (not the smoke sizes). Expect differences on other hardware; compare the ratios between
systems and the memory scaling more than the absolute numbers.

## Moss usage, internal APIs and side effects

- **Metered usage:** every run marked "creds" creates Moss sessions under your project, and the free tier
  meters them as voice-minutes. In our tests, queries, index builds and disk restores added usage; creating a
  session alone did not. Check your usage in the portal before long runs.
- **Nothing is pushed:** each run creates a session with a unique random name and never calls `push_index`,
  so no index is stored in Moss Cloud.
- **Internal APIs:** `moss_core.PyEmbeddingService` (in `bench_embed`, `bench_embed_tuning`, `moss_persist`)
  and `session._inner.query`, `_inner.save_to_disk` and `_inner.load_from_disk` (in `moss_persist`) are not
  public and may change between Moss versions. The results use moss 1.11.0 with inferedge-moss-core 0.23.1;
  newer releases exist.
- **Downloads and side files:** Moss downloads `moss-minilm` into `~/.cache/moss-models/` and creates
  `~/.moss/.moss-device-id`, both outside the repo. fastembed (Hugging Face) and Chroma (its S3 bucket)
  download into `.fastembed_cache/` and `.chroma_cache/` here; those caches, `.moss-sessions/`, `results/`
  and `data/arxiv/` are gitignored.

## Running with Claude Code

Point Claude Code at this file ("read benchmarks/LOCAL_BENCHMARKS.md and run the smoke test"). Ask it to:

- Run `./run_local.sh smoke` before anything else, and run benchmarks one at a time, always through
  `./run_local.sh run` so the watchdog applies.
- Ask you before every heavy run: `memory-repro`, `moss_mem 1000`, `bench_local moss`, `moss_ramp`,
  `doc_chunk_builtin ramp` or `run moss paper 1000`, and anything in `doc_chunk_eval`. Stop with
  `pkill -9 -f 'benchmarks/.venv/bin/python'`. `memory-repro` prompts on a terminal and refuses to run without
  one, so after you approve, the agent runs `./run_local.sh run moss_mem 100`, then `run moss_mem 1000`.
- Use `MOSS_ENV_FILE` for credentials and never open the `.env` file itself.
- Report numbers from the files the runs wrote in `results/`, not from memory.
