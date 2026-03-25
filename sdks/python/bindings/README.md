# Moss Python Bindings

This directory contains the [PyO3](https://pyo3.rs/) binding layer source for `inferedge-moss-core` — the native Rust extension that powers the [`moss`](../sdk/) Python SDK.

## What's here

These are the Rust-to-Python bindings used by the SDK. The source is published so you can see exactly what the native layer does:

- **`lib.rs`** — Module entry point, registers all Python-facing classes
- **`indexmanager.rs`** — Cloud index lifecycle (load, query, unload)
- **`manage/client.rs`** — Cloud REST API (create/delete indexes, add/remove docs, poll jobs)
- **`manage/types.rs`** — Job status, mutation result, and mutation option types
- **`models.rs`** — Python-facing data types (`DocumentInfo`, `SearchResult`, `QueryOptions`, etc.)

## Installation

These bindings are distributed as pre-built wheels on PyPI:

```bash
pip install inferedge-moss-core
```

Pre-built wheels are available for Python 3.10+ on Linux (x86_64, aarch64), macOS (x86_64, ARM), and Windows (x86_64).

**For most users**, install the SDK instead — it includes the bindings as a dependency:

```bash
pip install moss
```

## Requesting changes

If you need a feature or change in the native layer:

1. **Open an issue** at [github.com/usemoss/moss/issues](https://github.com/usemoss/moss/issues) describing the use case
2. The Moss team will evaluate, implement, and publish an updated wheel to PyPI

If you'd like to contribute a bindings-layer change directly, open a PR with your `.rs` changes. The Moss team will validate it against the internal build before merging.

## License

[BSD 2-Clause License](../sdk/LICENSE)
