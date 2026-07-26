# Contributing to ten-moss

## Setup

```bash
cd packages/ten-moss
uv sync
```

## Test & lint

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run ruff format --check .
```

Tests are offline (the Moss client is mocked) — no credentials required.
