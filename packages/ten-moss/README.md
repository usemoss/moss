# ten-moss

Ambient sub-10ms semantic retrieval for the [TEN Framework](https://github.com/ten-framework/ten-framework), powered by [Moss](https://moss.dev).

`MossRetrievalStore` loads a Moss index once and returns a formatted context
block for each user turn — drop it into a TEN control extension to ground your
voice agent's answers. Retrieval failures degrade to an empty string, so the
voice loop never stalls.

See `apps/ten-moss/` for a full runnable TEN voice-assistant example.

## Install

```bash
pip install ten-moss   # or: uv add ten-moss
```

## Usage

```python
from ten_moss import MossRetrievalStore

store = MossRetrievalStore(
    project_id="...", project_key="...", index_name="support-docs",
    top_k=5, alpha=0.8,
)
await store.load()                          # once, at startup
context = await store.retrieve(user_text)   # per turn; "" on no hits/error
```

Or build it from TEN properties:

```python
from ten_moss import MossRetrievalConfig, MossRetrievalStore

config = MossRetrievalConfig(**props)          # moss_* fields from property.json
store = MossRetrievalStore.from_config(config)
```

## Configuration (`MossRetrievalConfig`)

| Field | Default | Meaning |
| --- | --- | --- |
| `moss_project_id` | `""` | Moss project id |
| `moss_project_key` | `""` | Moss project key |
| `moss_index_name` | `""` | index to load and query |
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
