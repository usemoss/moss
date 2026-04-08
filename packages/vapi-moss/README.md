# vapi-moss

Moss semantic search integration for [VAPI](https://vapi.ai/) Custom Knowledge Base webhooks.

Provides `MossVapiSearch` — a framework-agnostic adapter that queries a preloaded Moss index and returns documents in VAPI's expected `{"content", "similarity"}` shape. Also includes `verify_vapi_signature` for webhook HMAC-SHA256 verification.

## Installation

```bash
pip install vapi-moss
```

## Quick Start

```python
from vapi_moss import MossVapiSearch

search = MossVapiSearch(
    project_id="your-id",
    project_key="your-key",
    index_name="my-faq-index",
)
await search.load_index()

result = await search.search("How do I return an item?")
print(result.documents)    # [{"content": "...", "similarity": 0.92}, ...]
print(result.time_taken_ms)  # 3
```

## Signature Verification

```python
from vapi_moss import verify_vapi_signature

is_valid = verify_vapi_signature(
    raw_body=request_bytes,
    signature_header=headers["x-vapi-signature"],
    secret="your-webhook-secret",
)
```

See [apps/vapi-moss](../../apps/vapi-moss/) for a complete FastAPI server example.
