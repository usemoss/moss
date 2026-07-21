# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-21

### Added
- `MossSessionManager.last_time_taken_ms` — the engine-measured retrieval time (ms) from the most recent `query_context` call (`SearchResult.time_taken_ms`); `None` before the first query or on error.
- `examples/latency_breakdown.py` — prints the one-time session-open cost and per-turn retrieval latency (engine `time_taken_ms` and wall-clock; p50/p95/mean).

### Changed
- First public release to PyPI (`pip install ten-moss`).

## [0.0.1] - 2026-07-15

### Added
- `MossSessionManager` — session-scoped Moss grounding for TEN extensions, built on the Moss Sessions API: `open`, `query_context`, `add_docs`, `get_docs`, `delete_docs`, `push_index`, `from_config`, `doc_count`.
- `MossSessionConfig` — standardized `moss_*` properties for TEN extensions. The project key is a masked `SecretStr`; `moss_top_k`/`moss_alpha`/`moss_max_context_chars` are range-validated; unset `moss_model_id` adopts the stored index's model; `moss_max_context_chars` caps the injected grounding block.
- `examples/create_index.py` — create and populate a demo index.
