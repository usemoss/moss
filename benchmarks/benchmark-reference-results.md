# Local benchmark reference results

Measured with the scripts in this directory; see [LOCAL_BENCHMARKS.md](LOCAL_BENCHMARKS.md) for how to rerun them.

## Environment
- **Machine:** Apple M5 Max, 18 cores, 128 GB RAM, macOS (Darwin 25.6).
- **Python:** 3.12.13 in a dedicated venv. `uv.lock` in this directory reproduces that environment exactly (`./run_local.sh setup`).
- **Versions:** moss 1.11.0, inferedge-moss-core 0.23.1, chromadb 1.5.9, lancedb 0.38.0, qdrant-client 1.19.0, fastembed 0.8.0, onnxruntime 1.30.0, onnx 1.22.0, pypdf 6.18.1, tokenizers 0.23.2, numpy 2.5.3.
- **Dates:** measured 2026-09-23 to 2026-09-25.
- **Protocol:** one run per configuration. Unless noted: 15 queries, 3 warmup rounds, then 50 × 15 = 750 measured sequential queries, top_k = 5, cosine similarity.

---

## 1. Query latency, 10k short docs, everything local
Script: `bench_local.py`. Moss embeds with its built-in `moss-minilm`; the others use fastembed `sentence-transformers/all-MiniLM-L6-v2`. The two models produce identical vectors (cosine 1.000000).

| System | End-to-end p50 / p95 / p99 (ms) | Search-only p50 (ms) | Peak RSS |
|---|---|---|---|
| Moss 1.11.0 | 1.33 / 1.55 / 1.70 | 0.47¹ | 10.7–11.2 GB |
| ChromaDB (HNSW) | 4.45 / 4.81 / 5.21 | 0.59 | 2.3 GB |
| LanceDB (IVF_HNSW_SQ index) | 5.55 / 6.16 / 6.62 | 1.55 | 2.5 GB |
| LanceDB (flat, no index) | 6.63 / 7.11 / 7.51 | 2.70 | 2.5 GB |
| Qdrant `:memory:` (always brute force) | 7.09 / 7.63 / 7.95 | 3.01 | 2.4 GB |
| ChromaDB, Chroma's own embedder with query padding off² | 1.50 / 7.49 / 8.01 | — | 2.5 GB |

¹ Measured separately on the custom-embedding path (`moss_persist.py build`).

² Its slow calls (62/750) all occurred in the first 10 rounds. Over rounds 40–49 only: Chroma 1.48 / 1.63 / 1.74 ms, against Moss 1.31 / 1.48 / 1.56 ms over the same rounds.

## 2. Query embedding, one query (same MiniLM weights)
Scripts: `bench_embed.py`, `bench_embed_tuning.py`. Rows marked † come from an ad-hoc check that is not one of the shipped scripts. All values are p50 in ms.

| Runtime / configuration | p50 (ms) |
|---|---|
| Moss native (`moss_core.PyEmbeddingService`, an internal API) | 0.83 |
| ONNX Runtime, no padding † | 0.98 |
| ONNX Runtime, padded to 128 tokens † | 3.37 |
| ONNX Runtime, padded to 256 tokens † | 5.68 |
| fastembed default (pads to 128) | 3.71 |
| fastembed with `threads` = 1 / 2 / 4 / 8 | 6.25 / 4.59 / 3.66 / 3.31 |
| fastembed with the CoreML execution provider | 15.55 |
| ONNX Runtime int8 quantized (cosine 0.91–0.96 vs fp32) | 4.07 |
| Chroma `DefaultEmbeddingFunction` (builds a new ONNX session per call) † | 35.2 |
| Chroma `ONNXMiniLM_L6_V2`, one reused instance (pads to 256) † | 5.94 |

## 3. Built-in ingest memory, short docs (median 24 tokens), one `add_docs` call per size
Script: `moss_ramp.py` (drives `moss_scale.py`). The ramp stopped before 100k docs because the projected peak was about 110 GB.

| Docs | Peak RSS | RSS after ingest | Query p50 (ms) |
|---|---|---|---|
| 1k | 1.7 GB | 1.1 GB | 0.97 |
| 2k | 3.1 GB | 2.1 GB | 1.02 |
| 4k | 4.6 GB | 3.4 GB | 1.24 |
| 8k | 9.4 GB | 6.9 GB | 1.29 |
| 16k | 17.9 GB | 12.9 GB | 1.35 |
| 32k | 33.9 GB | 25.6 GB | 1.48 |
| 64k | 69.8 GB | 52.7 GB | 1.79 |

The same 10k docs ingested on the custom-embedding path (precomputed vectors) peaked at about 1.1 GB (`moss_persist.py build`).

## 4. Ingest memory by docs per `add_docs` call (1,000 paper chunks, 192k tokens)
Script: `moss_mem.py`.

| Docs per call | Peak | After ingest | After deleting all docs | After re-ingest | After dropping the session | Ingest time |
|---|---|---|---|---|---|---|
| 1,000 | 14.5 GB | 8.5 GB | 8.5 GB | 15.8 GB (21.8 GB peak) | 2.8 GB | 19.4 s |
| 100 | 2.2 GB | 2.2 GB | 2.2 GB | 2.2 GB | 2.2 GB | 19.1 s |
| 1 | 0.49 GB | 0.24 GB | 0.24 GB | 0.24 GB | 0.24 GB | 33.0 s |

## 5. Built-in ingestion path, 1,000 docs
Script: `doc_chunk_builtin.py`.
- **paper:** the first 1,000 section-aware chunks from 10 arXiv PDFs, each under 256 tokens including special tokens, with a 32-token overlap. Median 222 tokens, 192k tokens in total.
- **small:** the first 1,000 docs of `bench_100k_docs.json`, 24k tokens in total.

| Run | Ingest | Peak RSS | End-to-end p50 / p95 / p99 (ms) |
|---|---|---|---|
| Moss, paper 125 / 250 / 500 / 1,000 | 52 / 52 / 51 / 50 docs/s | 2.0 / 3.9 / 6.7 / 14.5 GB | 1.42 / 1.44 / 1.44 / 1.47 (p50) |
| Moss, small 1,000 | 572 docs/s | 1.7 GB | 1.47 / 1.92 / 1.99 |
| Chroma default embedder, paper 1,000 | 162 docs/s | 0.98 GB | 38.10 / 41.58 / 45.35 |
| Chroma default embedder, small 1,000 | 173 docs/s | 0.97 GB | 38.08 / 41.16 / 43.81 |
| Chroma reused embedder, paper 1,000 | 180 docs/s | 0.88 GB | 8.02 / 12.78 / 13.16 |
| Chroma reused embedder, small 1,000 | 178 docs/s | 0.87 GB | 6.47 / 6.94 / 9.48 |
| Chroma unpadded queries, paper 1,000 | 173 docs/s | 1.03 GB | 1.96 / 7.35 / 8.02³ |

Moss and Chroma returned identical ordered top-5 results for all 15 queries in every paired run.

³ Over rounds 40–49 only: 1.98 / 2.81 / 3.24 ms, against Moss 1.47 / 1.92 / 1.96 ms.

## 6. Batching and padding throughput (plain ONNX Runtime MiniLM, docs/s)
Script: `batch_padding.py`. Vectors are identical to unbatched in every case (minimum cosine 1.000000).

| Strategy | Paper chunks | Short docs |
|---|---|---|
| Unbatched, unpadded | 200 | 934 |
| Batch of 32, fixed pad to 256 | 193 | 183 |
| Batch of 32, pad to longest in batch | 194 | 1,712 |
| Batch of 32, pad to longest, sorted by length | 242 | 2,024 |
| *Moss built-in ingest, for comparison* | *50* | *572* |

## 7. Precomputed large-model vectors (qwen3-embedding 4B, 2560 dimensions), 126 docs
Script: `doc_chunk_eval.py`. Requires Ollama with `qwen3-embedding:4b-q8_0`.
- **Search only, p50:** Moss 0.194 ms (paper) / 0.168 ms (small); Chroma 0.572 / 0.573 ms. Identical top-5 results.
- **Query embedding via Ollama over HTTP:** p50 56.85 ms.
- **Model memory:** 10.96 GiB while loaded (Ollama `/api/ps`; default 40,960-token context), against a 4.08 GB weights file.
- **Document embedding throughput:** 9.2 docs/s (3,239 tokens/s) for paper chunks; 21.9 docs/s (587 tokens/s) for short docs.

## 8. Persistence (private API)
Script: `moss_persist.py`.
- **10k docs, custom-embedding session:** `_inner.save_to_disk` wrote 16 MB in 0.05 s. `load_from_disk` in a new process took 0.06 s, against a 16.1 s rebuild, with identical top-5 results.
- **Invalid credentials:** constructing the native session fails with `Authentication failed: invalid credentials`.

## Caveats
- One machine and one run per configuration. Concurrency and recall were not tested.
- `moss_core.PyEmbeddingService` and `session._inner.*` are internal APIs and may change.
- Newer releases exist (moss 1.13.0+), so results may differ on them.
