# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## What This Repo Is

Moss is a real-time semantic search runtime for AI agents targeting sub-10ms query latency. The runtime runs on-device using bundled embedding models (`moss-minilm`) — no external embedding API calls are needed. The cloud layer handles project management and index distribution; the local layer handles querying.

This repository contains the **multi-language SDKs**, **framework integrations** (cookbooks), and **application examples**. It is NOT the core Rust engine — that ships as pre-compiled native bindings (`inferedge-moss-core` / `@moss-dev/moss-core` / `moss_core`).

## Repository Layout

```
sdks/
  python/sdk/      — Python SDK (PyPI: moss), Python 3.10+
  javascript/sdk/  — JS/TS SDK (npm: @moss-dev/moss), ESM-only
  elixir/sdk/      — Elixir SDK (Hex: moss)
examples/
  python/          — Standalone Python usage examples
  javascript/      — Standalone TS usage examples
  cookbook/        — Framework integrations (LangChain, DSPy, Pipecat, etc.)
apps/
  next-js/         — Next.js semantic search UI
  pipecat-moss/    — Pipecat voice agent integration
  livekit-moss-vercel/ — LiveKit + Vercel voice agent
packages/
  vitepress-plugin-moss/ — VitePress search plugin
  vercel-sdk/            — Vercel AI SDK integration
  pipecat-moss/          — Pipecat Python package
  moss-cli/              — CLI tools for index management
```

## Commands

### Python SDK (`sdks/python/sdk/`)

```bash
cd sdks/python/sdk
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest tests/                    # run all tests (E2E tests auto-skip without credentials)
pytest tests/test_client.py      # run a single test file
black src/ tests/                # format
isort src/ tests/                # sort imports
mypy --ignore-missing-imports src/  # type check
ruff check .                     # lint (used in CI)
```

### JavaScript/TypeScript SDK (`sdks/javascript/sdk/`)

```bash
cd sdks/javascript/sdk
npm install
npm run build      # compile TS → dist/
npm test           # vitest run
npm run test:watch # vitest watch mode
npm run lint       # eslint
npm run format     # prettier
```

### Root (examples only — not the SDK)

```bash
npm run type-check  # TS type check across examples/javascript and apps/next-js
npm run lint        # eslint across examples/javascript and apps/next-js
```

### Elixir SDK (`sdks/elixir/sdk/`)

```bash
cd sdks/elixir/sdk
mix deps.get
mix test
```

## Architecture: Two-Layer Design

Every SDK has the same two-layer structure:

```
Your Code
   ↓
SDK layer (pure language, open source)
   └─ MossClient — async API surface for index and document operations
   └─ Communicates with Moss Cloud (HTTPS) for mutations and distribution
   ↓
Native bindings (Rust, pre-compiled, published as separate package)
   └─ ManageClient / IndexManager — handles embedding, indexing, local search
   └─ Imported as: inferedge-moss-core (Python), @moss-dev/moss-core (JS), moss_core (Elixir)
```

The Python `MossClient` in [sdks/python/sdk/src/moss/client/moss_client.py](sdks/python/sdk/src/moss/client/moss_client.py) re-exports types from `moss_core` and wraps `ManageClient` + `IndexManager` from the native layer. The JS SDK follows the same pattern in [sdks/javascript/sdk/src/client/](sdks/javascript/sdk/src/client/).

**Key invariant:** Mutations (create/add/delete) go to the cloud via `ManageClient`. Queries use the local `IndexManager` when an index is loaded; otherwise fall back to the cloud query API.

## Environment Variables

```bash
MOSS_PROJECT_ID=...          # required for all SDK usage
MOSS_PROJECT_KEY=...          # required for all SDK usage
MOSS_CLOUD_API_MANAGE_URL=... # optional, override for local dev
MOSS_CLOUD_QUERY_URL=...      # optional, override for local dev
```

Copy `.env.example` to `.env` in the relevant example/app directory.

## SDK Patterns to Follow

When adding examples or cookbook integrations, follow the existing patterns:

- **Python examples**: Import `MossClient, DocumentInfo` from `moss`; use `async/await`; store credentials in env vars via `python-dotenv`
- **JS examples**: Import from `@moss-dev/moss`; ESM only (`"type": "module"`); use `tsx` to run `.ts` files directly
- **Framework cookbooks**: Each lives in `examples/cookbook/<name>/` with its own `pyproject.toml` or `package.json`, a `README.md`, and minimal dependencies on top of the core SDK

## Testing Notes

- E2E and integration tests require `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`; they auto-skip gracefully when credentials are absent
- CI runs Python SDK tests across versions 3.10–3.14 in a GitHub Actions matrix using `pytest` directly
- CI lints Python with `ruff` and type-checks with `mypy`; format locally with `black` + `isort`
- JS tests use Vitest; CI runs on Node 20

## CI Workflows

The `.github/workflows/ci.yml` pipeline runs on push to `main` and on PRs:
- `python-lint` — ruff on examples and apps
- `python-sdk-test` — matrix over Python 3.10–3.14
- `javascript-lint` — eslint
- Separate release workflows publish to PyPI / npm on tagged releases
