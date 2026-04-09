# Moss Elixir SDK

Source for the [`moss`](https://hex.pm/packages/moss) Elixir package.

## Architecture

```
                    ┌──────────────────────────────────┐
                    │      Your application code       │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │  moss  (Elixir)                  │  ← sdk/
                    │  Moss.Client — API for indexing,  │
                    │  querying, sessions, management   │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │  moss_core  (Rust/Rustler NIF)   │  ← bindings/
                    │  SessionIndex, IndexManager,     │
                    │  ManageClient, data models       │
                    └──────────────────────────────────┘
```

| Directory | Package | Description |
|-----------|---------|-------------|
| [`sdk/`](./sdk/) | `moss` | Elixir SDK. Fully open-source — install, build, modify, contribute. |
| [`bindings/`](./bindings/) | `moss_core` | Native Rust/Rustler NIF bindings for the Moss engine. Source available for reference and debugging. Pre-built NIFs via [RustlerPrecompiled](https://hex.pm/packages/moss_core). Feature requests and bugs → [open an issue](https://github.com/usemoss/moss/issues). |

## Quick start

```elixir
# mix.exs
{:moss, "~> 1.0"}
```

```elixir
{:ok, client} = Moss.Client.new("your_project_id", "your_project_key")

Moss.Client.create_index(client, "support-docs", [
  %{id: "1", text: "Refunds are processed within 3-5 business days."},
  %{id: "2", text: "You can track your order on the dashboard."}
])

Moss.Client.load_index(client, "support-docs")
{:ok, results} = Moss.Client.query(client, "support-docs", "how long do refunds take?", top_k: 3)

for doc <- results.docs do
  IO.puts("[#{Float.round(doc.score, 3)}] #{doc.text}")
end
```

See [`sdk/README.md`](./sdk/README.md) for the full API reference.

## Contributing

**SDK (`sdk/`)** — open for contributions:

```bash
cd sdk
mix deps.get
mix test
```

**Bindings (`bindings/`)** — source is published for reference. To request changes or report bugs, [open an issue](https://github.com/usemoss/moss/issues).

## License

[BSD 2-Clause License](./sdk/LICENSE)
