# Moss Python SDK

Source for the [`moss`](https://pypi.org/project/moss/) Python package.

## Architecture

```
                    ┌──────────────────────────────────┐
                    │      Your application code       │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │  moss  (pure Python)             │  ← sdk/
                    │  MossClient — async API for      │
                    │  indexing, querying, management  │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │  moss-core  (Rust/PyO3)          │  ← bindings/
                    │  IndexManager, ManageClient,     │
                    │  hybrid search, data models      │
                    └──────────────────────────────────┘
```

| Directory | Package | Description |
|-----------|---------|-------------|
| [`sdk/`](./sdk/) | `moss` | Pure Python SDK. Fully open-source — install, build, modify, contribute. |
| [`bindings/`](./bindings/) | `inferedge-moss-core` | Native Rust/PyO3 bindings for the Moss engine. Source available for reference and debugging. Pre-built wheels on [PyPI](https://pypi.org/project/inferedge-moss-core/). Feature requests and bugs → [open an issue](https://github.com/usemoss/moss/issues). |

## Quick start

```bash
pip install moss
```

```python
from moss import MossClient, DocumentInfo, QueryOptions

client = MossClient("your_project_id", "your_project_key")

await client.create_index("support-docs", [
    DocumentInfo(id="1", text="Refunds are processed within 3-5 business days."),
    DocumentInfo(id="2", text="You can track your order on the dashboard."),
])

await client.load_index("support-docs")
results = await client.query("support-docs", "how long do refunds take?", QueryOptions(top_k=3))

for doc in results.docs:
    print(f"[{doc.score:.3f}] {doc.text}")
```

See [`sdk/README.md`](./sdk/README.md) for the full API reference.

## Contributing

**SDK (`sdk/`)** — open for contributions:

```bash
cd sdk
pip install -e ".[dev]"
pytest tests/                # cloud tests auto-skip without credentials
```

**Bindings (`bindings/`)** — source is published for reference. To request changes or report bugs, [open an issue](https://github.com/usemoss/moss/issues).

## License

[BSD 2-Clause License](./sdk/LICENSE)
