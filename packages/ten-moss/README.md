# ten-moss

A **Moss session manager** for the [TEN Framework](https://github.com/ten-framework/ten-framework), powered by [Moss](https://moss.dev).

`MossSessionManager` wraps a [Moss session](https://docs.moss.dev/docs/reference/python/sessions) — a local, in-process index (~1–10ms, no cloud round-trip) — and manages a voice agent's session-scoped grounding. It **abstracts the query**: a TEN control extension asks for grounding with `context_for(text)` and never issues raw retrieval. The session also accepts runtime writes (`remember`) and can be persisted for durability or cross-agent handoff (`persist`). Lookups degrade to an empty string on error, so the voice loop never stalls.

See `apps/ten-moss/` for a full runnable TEN voice-assistant example.

## Install

```bash
pip install ten-moss   # or: uv add ten-moss
```

## Usage

```python
from ten_moss import MossSessionManager

session = MossSessionManager(
    project_id="...", project_key="...", index_name="support-docs",
    top_k=5, alpha=0.8,
)
await session.start()                          # open the session (create-or-resume)
context = await session.context_for(user_text) # per turn; "" on no hits/error
# optional: write runtime context, then persist for handoff
await session.remember(user_text)
await session.persist()
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
| `await start()` | Open the Moss session (create-or-resume the index) |
| `await context_for(text) -> str` | Grounding block for this turn; `""` on blank/no-hit/error |
| `await remember(text, *, id=None, metadata=None)` | Write a turn/fact into the session |
| `await persist()` | Persist the session to the cloud (durability / handoff) |
| `doc_count` | Documents currently in the session |

## Configuration (`MossSessionConfig`)

| Field | Default | Meaning |
| --- | --- | --- |
| `moss_project_id` | `""` | Moss project id |
| `moss_project_key` | `""` | Moss project key |
| `moss_index_name` | `""` | session index to open (create-or-resume) |
| `moss_model_id` | `"moss-minilm"` | embedding model for the session |
| `moss_top_k` | `5` | results per query |
| `moss_alpha` | `0.8` | semantic/keyword blend (1.0 semantic, 0.0 keyword) |
| `moss_context_header` | `"Relevant knowledge from Moss:"` | header of the injected block |
| `enable_moss` | `true` | master toggle |

## Create a demo index

```bash
cp .env.example .env   # fill in your Moss credentials
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
