# ten-moss

A **Moss session manager** for the [TEN Framework](https://github.com/ten-framework/ten-framework), powered by [Moss](https://moss.dev).

`MossSessionManager` wraps a [Moss session](https://docs.moss.dev/docs/reference/python/sessions) — a local, in-process index (~1–10ms, no cloud round-trip) — and mirrors the Moss Sessions SDK (`open`, `add_docs`, `get_docs`, `delete_docs`, `push_index`, `doc_count`). It adds one convenience for grounding: `query_context(text)` returns an injection-ready context block (not a raw `SearchResult`), and degrades to an empty string on no-hit/error so the voice loop never stalls.

A full runnable TEN voice-assistant example ships in the companion `apps/ten-moss/` app (see the app PR / the `apps/ten-moss/` directory once both land on `main`).

## Install

```bash
pip install ten-moss   # or: uv add ten-moss
```

## Usage

```python
from ten_moss import DocumentInfo, MossSessionManager

session = MossSessionManager(
    project_id="...", project_key="...", index_name="support-docs",
    top_k=5, alpha=0.8,
)
await session.open()                             # open the session (create-or-resume)
context = await session.query_context(user_text) # per turn; "" on no hits/error
# optional: write runtime context, then persist for handoff
await session.add_docs([DocumentInfo(id="turn-1", text=user_text)])
await session.push_index()
```

Or build it from TEN properties:

```python
from ten_moss import MossSessionConfig, MossSessionManager

config = MossSessionConfig(**props)                # moss_* fields from property.json
session = MossSessionManager.from_config(config)
```

## Public API (`MossSessionManager`)

| Method | Purpose |
| --- | --- |
| `await open()` | Open the Moss session (create-or-resume the index) |
| `await query_context(text) -> str` | Grounding block for this turn; `""` on blank/no-hit/error |
| `await add_docs(docs)` | Add/update documents in the session (mirrors `SessionIndex.add_docs`) |
| `await get_docs()` | Documents currently in the session |
| `await delete_docs(ids)` | Delete documents from the session by id |
| `await push_index()` | Persist the session to the cloud (durability / handoff) |
| `doc_count` | Number of documents in the session |

When built with `enable_moss=false`, no client is created and every method is a safe no-op.

## Configuration (`MossSessionConfig`)

| Field | Default | Meaning |
| --- | --- | --- |
| `moss_project_id` | `""` | Moss project id |
| `moss_project_key` | `""` | Moss project key (stored as a masked `SecretStr`) |
| `moss_index_name` | `""` | session index to open (create-or-resume) |
| `moss_model_id` | `""` | embedding model; empty = adopt the stored index's model (or the SDK default for a new index). `"custom"` is rejected — it needs a query embedding this manager can't supply. |
| `moss_top_k` | `5` | results per query (must be > 0) |
| `moss_alpha` | `0.8` | semantic/keyword blend, 0.0–1.0 (1.0 semantic, 0.0 keyword) |
| `moss_context_header` | `"Relevant knowledge from Moss:"` | header of the injected block |
| `moss_max_context_chars` | `2000` | cap on the injected grounding block (0 = unlimited) |
| `enable_moss` | `true` | master toggle |

`moss_top_k`, `moss_alpha`, and `moss_max_context_chars` are validated at construction — an out-of-range value raises a clear error instead of failing later.

## Create a demo index

The example loads `.env` via `python-dotenv` if it's installed; otherwise export the
variables directly.

```bash
pip install ten-moss python-dotenv     # python-dotenv is only needed for .env loading
cp .env.example .env                   # fill in your Moss credentials
python examples/create_index.py
# — or, without python-dotenv —
export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=...
python examples/create_index.py
```

## Development

```bash
uv sync
uv run pytest tests/ -v
uv run ruff check .
```

Tests are offline (the Moss client is mocked) — no credentials required.

## License

BSD-2-Clause.
