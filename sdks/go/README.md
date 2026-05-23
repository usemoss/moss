# Moss Go SDK

The Go work now has the same two-layer direction as the other Moss SDKs:

- `sdks/go/sdk/` contains the public Go SDK
- `sdks/go/bindings/` wraps the native `libmoss` runtime via CGO

Current status:

- bindings-backed manage operations for mutations and metadata reads
- local `LoadIndex` / `UnloadIndex` / local `Query` via `libmoss`
- examples and unit tests
- env-gated integration test scaffold

Important note:

- all runtime operations require the `libmoss` C SDK plus `-tags libmoss`

The public SDK module lives under [`sdks/go/sdk/`](./sdk/), and the native
bindings module lives under [`sdks/go/bindings/`](./bindings/).
