# Agora custom-llm + Moss

Agora cloud owns STT and TTS. This process owns `/chat/completions` and runs Moss next to the LLM.

This is not `apps/agora-moss`. That demo is MCP (Agora calls `search_knowledge_base`). Here Agora only sees an OpenAI-compatible URL.

Same 10 FAQs as `apps/ten-moss/data/knowledge.jsonl`.

## Copy these

| File | Why |
| --- | --- |
| `README.md` | this page |
| `server/src/llm.py` | one turn, both modes |
| `create_index.py` + `data/knowledge.jsonl` | same corpus as TEN |
| `server/.env.example` | `MOSS_*`, `CUSTOM_LLM_*`, `UPSTREAM_LLM_*` |

## One turn

**Ambient** (`/llm/chat/completions`, default): take the last user text, `query_context`, prepend, call the upstream model, stream SSE.

**Tool** (`/llm-tools/chat/completions`): give the upstream model `search_knowledge_base`. If it calls the tool, run Moss here (max 2 times). Stream only the final answer. Agora never sees the tool.

`MOSS_MODE=ambient|tool` picks the mode when you run `llm.py` alone.

## Run with no LLM keys

```bash
cd apps/agora-custom-llm-moss
python -m pip install -r server/requirements.txt
python server/src/llm.py --mock --doctor
```

Doctor hits both modes and checks that a missing `Authorization: Bearer` is rejected when mock is off.

```bash
python server/src/llm.py --mock --mode ambient   # :8001/chat/completions
python server/src/server.py                      # /llm ambient, /llm-tools tool
```

## Run with a real index

```bash
cp server/.env.example server/.env   # fill MOSS_* and a unique CUSTOM_LLM_API_KEY
python create_index.py
python server/src/server.py
ngrok http 8000
# CUSTOM_LLM_URL=https://<tunnel>/llm/chat/completions
# tool URL:     https://<tunnel>/llm-tools/chat/completions
```

Set `CUSTOM_LLM_API_KEY` to a unique value before exposing the URL. If it is empty, every request is rejected, including any Bearer token. Send `Authorization: Bearer $CUSTOM_LLM_API_KEY`. If Moss is unset or errors, the handler returns empty context and still streams.

Offline table: `python apps/ten-moss/bench/run.py --echo-grounding`

`llm.py` keeps the Agora recipe SSE contract (MIT). The rest of this directory is BSD-2-Clause.
