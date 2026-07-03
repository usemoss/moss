# Moss Integration

## Install

```bash
./scripts/setup-moss-venv.sh
export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=...
```

Uses **PyPI `moss>=1.6.0`**, not editable install from `vendor/moss/sdks/python/sdk` (main branch lacks sessions).

`vendor/moss` submodule is for examples/reference only.

## Worker JSON protocol (line-delimited)

### Request → Response

| action | input | output |
|--------|-------|--------|
| `ping` | `{}` | `{"status":"ok"}` |
| `init_session` | `{"index_name":"documents"}` | `{"status":"ok","doc_count":N}` |
| `add_docs` | `{"files":["/path/a.md"]}` | `{"status":"ok","added":N,"updated":M}` |
| `query` | `{"query":"text","top_k":5}` | `{"results":[...],"timing_ms":4.2}` |
| `push_index` | `{}` | `{"status":"ok","doc_count":N}` |
| `clear_index` | `{}` | `{"status":"ok"}` |

### Error shape

```json
{"error": "message"}
```

## Moss SDK calls (verified PyPI 1.6.0)

```python
client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
session = await client.session(index_name="documents")
await session.add_docs([DocumentInfo(id=path, text=content, metadata={"path": path, "filename": name})])
results = await session.query("query", QueryOptions(top_k=5, alpha=0.6))
await session.push_index()  # optional cloud sync
```

## Text extraction

- Supported: `.md`, `.txt`, `.rtf`, `.html` (BeautifulSoup), `.pdf` (pypdf), `.docx` (python-docx)
- Skipped: `.notes`
- Chunks: ~1800 chars with 300 char overlap; IDs like `path#chunk-0001`

## Dev credentials

Priority: `MOSS_PROJECT_ID`/`MOSS_PROJECT_KEY` env → Keychain → repo `.env` via `DotEnvLoader`
