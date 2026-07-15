# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-07-15

### Added
- `MossSessionManager` — session-scoped Moss grounding for TEN extensions, built on the Moss Sessions API: `open`, `query_context`, `add_docs`, `get_docs`, `delete_docs`, `push_index`, `from_config`, `doc_count`.
- `MossSessionConfig` — standardized `moss_*` properties for TEN extensions.
- `examples/create_index.py` — create and populate a demo index.
