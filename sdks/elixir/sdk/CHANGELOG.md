# Changelog

## [1.0.1] - 2026-04-05

### Changed

- Bumped `moss_core` dependency to 0.9.0.
- Session authentication now uses short-lived JWT tokens (enterprise plan required).
- Removed `validate_credentials` call from `Client.session/3`; credential exchange happens inside the Rust core during session init.
- Updated package metadata and README.

---

## [1.0.0] - 2026-04-01

### Changed

- Renamed package from `moss_session` to `moss`.
- Published as a public Hex package (no longer requires `organization: "moss"`).
- Bumped version to 1.0.0 stable.

---

## [1.0.0-beta.5] - 2026-03-16

### Changed

- Bumped `moss_core` dependency to 0.8.7, which fixes the precompiled NIF tarball for macOS — the file inside the archive is now named with the versioned filename so RustlerPrecompiled places it correctly in `priv/native`.

---

## [1.0.0-beta.4] - 2026-03-16

### Changed

- Bumped `moss_core` dependency to 0.8.6, which fixes precompiled NIF packaging for macOS — the binary is now correctly distributed as `.so` (required by RustlerPrecompiled) instead of `.dylib`.

---

## [1.0.0-beta.3] - 2026-03-16

### Changed

- Bumped `moss_core` dependency to 0.8.5.

---

## [1.0.0-beta.1] - 2026-03-12

Initial release of the `moss_session` Elixir SDK (later renamed to `moss` in 1.0.0) with local-first session indexing.

### Added

- **`Moss.Client`** — single entry point for all operations
  - `new/3` — creates a client; starts an internal local index manager
  - `session/3` — auto-loads from cloud if the named index exists; starts empty otherwise; pre-warms built-in models (`"moss-minilm"` / `"moss-mediumlm"`) to eliminate cold-start delay on first query
  - Cloud CRUD: `create_index/4` (model_id optional, defaults to `"moss-minilm"`), `add_docs/4`, `delete_docs/3`, `get_job_status/2`, `get_index/2`, `list_indexes/1`, `delete_index/2`, `get_docs/3`
  - Local index ops: `load_index/3`, `unload_index/2`, `has_index/2`, `query/4`, `refresh_index/2`, `get_index_info/2`
  - Generates a per-client UUID (`client_id`) propagated to all sessions and managers for telemetry correlation
- **`Moss.Session`** GenServer — local in-session index backed by Rust core
  - `add_docs/3` — built-in models embed automatically; `model_id: "custom"` reads `.embedding` from each `DocumentInfo`; returns `{added, updated}`
  - `delete_docs/2` — remove documents by ID
  - `get_docs/2` — retrieve documents (optionally filtered by ID list)
  - `query/3` — semantic search; built-in models embed automatically; `model_id: "custom"` requires `embedding:` opt; accepts metadata filters
  - `load_index/2` — load an existing cloud index into the session
  - `push_index/1` — push local index to cloud (create or replace); flushes telemetry
- **`Moss.Models`** — Elixir structs: `DocumentInfo`, `SearchResult`, `QueryResultDoc`, `IndexInfo`, `PushIndexResult`, `RefreshResult`, `SerializedIndex`, `MutationResult`, `JobStatusResponse`, `CredentialsInfo`, `ModelRef`
- **Metadata filtering** — all query functions accept `:filter` map with full operator support
  - Field conditions: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$near`
  - Logical combinators: `$and`, `$or` (fully nestable)
- **Background telemetry** — aggregated telemetry handled by the Rust core
- **Built-in models** — `"moss-minilm"` (fast) and `"moss-mediumlm"` (higher quality); embedding computation runs entirely in the Rust core via ONNX Runtime
- **`model_id: "custom"`** — bring your own pre-computed embeddings; no local model required
