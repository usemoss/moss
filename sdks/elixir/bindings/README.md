# moss_core

`moss_core` is the Rustler NIF layer that powers the `moss` Elixir SDK. It exposes the high-performance Rust core as native BEAM functions.

## Overview

This package is a low-level NIF dependency and is not intended for direct use. For most use cases, add the higher-level SDK instead:

```elixir
# mix.exs
defp deps do
  [{:moss, "~> 1.0"}]
end
```

## What's inside

`moss_core` wraps three core Rust types via Rustler:

| Resource | Description |
|---|---|
| `SessionResource` | Local in-session index — add, query, push to cloud |
| `ManagerResource` | Cloud index manager — load, cache, and query cloud indexes |
| `ManageResource` | Cloud CRUD client — create, add docs, get job status, etc. |

All NIF functions are declared in `MossCore.Nif`. I/O-bound operations (load, push, cloud calls) run on Erlang dirty schedulers and do not block the main scheduler.

## Building locally

```bash
cd sdks/elixir/bindings
mix deps.get
mix compile          # compiles the Rust NIF in debug mode
MIX_ENV=prod mix compile  # release build
```

Requires Rust stable toolchain (`rustup install stable`).

## Related packages

- [`moss`](https://hex.pm/packages/moss) — Complete Elixir SDK with cloud integration
- [`moss`](https://pypi.org/project/moss/) — Python SDK
- [`@moss-dev/moss`](https://www.npmjs.com/package/@moss-dev/moss) — JavaScript/TypeScript SDK

## License

This package is licensed under the [BSD 2-Clause License](./LICENSE).

## Contact

For support, commercial licensing, or partnership inquiries: [contact@moss.dev](mailto:contact@moss.dev)
