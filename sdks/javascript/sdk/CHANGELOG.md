# Changelog

## [1.0.0] - 2026-04-01

### Architecture

- **Rust-native core**: The SDK now delegates all index management, querying, and embedding generation to `@moss-dev/moss-core` (Rust via NAPI-RS), replacing the previous pure-JavaScript implementations
- **Node-only**: Dropped browser/WASM support; the SDK targets Node.js 20+ exclusively
- Query embeddings are now generated in Rust (`queryText` / `loadQueryModel`), matching the Python SDK architecture

### Changed

- Package renamed from `@inferedge/moss` to `@moss-dev/moss`
- NAPI binding renamed from `moss-core` to `@moss-dev/moss-core` (v0.8.7, tracking Rust core version)
- `query()` uses Rust-native `queryText()` for local queries (no JS embedding pipeline)
- `query()` with `embedding` option uses Rust `query()` directly
- `query()` falls back to cloud HTTP when index is not loaded locally

## [1.0.0-beta.8] - 2026-03-30

### Added
- **Filesystem Index Caching**: `loadIndex()` now accepts an optional `cachePath` in `LoadIndexOptions` to cache index binaries and documents to disk (Node.js/Bun only)
  - Cache is automatically invalidated when the cloud index is updated
  - Auto-refresh also persists refreshed data to the cache
  - Atomic writes prevent cache corruption from partial/interrupted writes
  - Path traversal protection on index names
  - Graceful fallback to re-download if cached data is corrupted
- **Metadata Filtering**: `query()` now accepts an optional `filter` in `QueryOptions` to narrow results by document metadata on locally loaded indexes
  - Comparison operators: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`
  - Set operators: `$in`, `$nin`
  - Composable with `$and` / `$or` for complex predicates (supports arbitrary nesting)
  - Numeric coercion: number filter values are automatically stringified for consistent matching
- **Geo-distance filtering**: new `$near` operator filters documents by haversine distance from a `"lat,lng,radiusMeters"` value
- New exported types: `FilterCondition`, `MetadataFilter`

## [1.0.0-beta.7] - 2026-02-18

### Added
- Async job-based mutations (`createIndex`, `addDocs`, `deleteDocs`) with built-in polling and `onProgress` callbacks
- Large index support — up to 100k documents via presigned upload + server-side build
- New binary index format with smaller payloads and faster deserialization; existing indexes using the previous format are still supported

## [1.0.0-beta.6] - 2026-02-02

### Added
- **Hot Reload & Auto-Refresh**: Indexes can now automatically detect and reload when updated in the cloud.
  - `loadIndex()` now accepts optional `LoadIndexOptions` with `autoRefresh` and `pollingIntervalInSeconds` parameters
  - When `autoRefresh` is enabled, the SDK polls for updates at the configured interval (default: 600 seconds)
  - To stop auto-refresh, call `loadIndex()` again without the `autoRefresh` option
- `loadIndex()` now allows reloading an already-loaded index (previously threw an error)

## [1.0.0-beta.5] - 2025-01-29

### Added
- Query optimizations for custom-embedding workflow

## [1.0.0-beta.4] - 2025-01-28

### Fixed

- Fixed `ReferenceError: process is not defined` crash in browser environments. The SDK now works seamlessly across all JavaScript runtimes including browsers, Node.js, Deno, and Bun.

## [1.0.0-beta.3] - 2025-01-24

### Added

- Support for user-supplied document embeddings during ingestion. The SDK supports optional `embedding` arrays in `DocumentInfo` payloads without using the native embedding service from moss.
- Query overloads now accept `QueryOptions` so users can provide a custom embedding alongside query text.
- Relaxed `modelId` requirement when creating indexes. The SDK aligns with the service default of `moss-minilm` when no explicit model is provided.
- `query()` now automatically falls back to the cloud API when the index is not loaded locally, enabling queries without requiring `loadIndex()` first.

### Enhancements

- New service endpoint with significant infrastructure upgrades. Management operations are now ~3× faster across most real-world use cases, providing faster index operations while also supporting larger payloads.

## [1.0.0-beta.2] - 2025-11-30

### Fixed

- Fixed ESM (ES Module) import compatibility issue. The package now correctly exports as an ES module and can be imported using standard ESM syntax.

### Upgrade Instructions

- Migrate from CommonJS (`require`) to ES Module syntax (`import`).

## [1.0.0-beta.1] - 2025-10-01

Initial release of @moss-dev/moss with core features:

- Semantic search using transformer-based embeddings
- Lightweight embedding models for edge computing; supports proprietary "moss-minilm" and "moss-mediumlm" models
- Multi-index support for isolated search spaces
- Add, update, and remove documents across indexes
- Blazing fast querying support after loading indexes
- TypeScript support with full type definitions
