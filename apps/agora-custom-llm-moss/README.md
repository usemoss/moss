# Agora custom-llm + Moss

A copy-paste custom LLM for [Agora Conversational AI](https://recipes.agora.io/recipes/custom-llm). Agora cloud owns STT/TTS. This process owns `/chat/completions` and runs Moss **in the middleware**.

This is not `apps/agora-moss` (that demo is MCP: Agora calls `search_knowledge_base`). Here Agora only sees an OpenAI-compatible URL.

Same 10 FAQs as `apps/ten-moss/data/knowledge.jsonl`.

## What a stranger copies

| File | Why |
| --- | --- |
| `README.md` | this page |
| `server/src/llm.py` | the whole Moss story (ambient prepend vs tool loop) |
| `create_index.py` + `data/knowledge.jsonl` | identical corpus as TEN |
| `server/.env.example` | `MOSS_*`, `CUSTOM_LLM_*`, `UPSTREAM_LLM_*` |

## Two entrypoints, one index

| URL | Mode | What happens on a turn |
| --- | --- | --- |
| `/llm/chat/completions` | ambient (default) | extract last user text -> `query_context` -> prepend -> upstream LLM -> SSE |
| `/llm-tools/chat/completions` | tool | advertise `search_knowledge_base` to the **upstream** LLM, run Moss in-process, stream only the final answer. Cap 2 Moss calls. Agora never sees the tool. |

`MOSS_MODE=ambient|tool` selects the mode when you run `llm.py` alone.

## Quick start (zero LLM keys)

```bash
cd apps/agora-custom-llm-moss
python -m pip install -r server/requirements.txt
python server/src/llm.py --mock --doctor
```

`--doctor` hits ambient + tool in-process and checks that a missing `Authorization: Bearer` is rejected when mock is off. No Moss keys, no OpenAI keys, no Agora.

Mock server (Agora can call this through ngrok):

```bash
python server/src/llm.py --mock --mode ambient
# http://127.0.0.1:8001/chat/completions
```

Both mounts on one port:

```bash
python server/src/server.py
# /llm        ambient
# /llm-tools  tool
```

## With a real index

```bash
cp server/.env.example server/.env
# fill MOSS_PROJECT_ID / MOSS_PROJECT_KEY / MOSS_INDEX_NAME
python create_index.py
# optional: UPSTREAM_LLM_API_KEY for a real model (leave MOCK unset)
python server/src/server.py
ngrok http 8000
# CUSTOM_LLM_URL=https://<tunnel>/llm/chat/completions
# tool URL:     https://<tunnel>/llm-tools/chat/completions
```

Point Agora's custom-llm vendor at that public URL. Send `Authorization: Bearer $CUSTOM_LLM_API_KEY`.

## Fail-open

If Moss is unset, fails to import, times out, or raises, the handler returns empty context and still streams an answer. The SSE loop does not die.

## Offline bench

The published gold-phrase table lives next to the TEN app:

```bash
python apps/ten-moss/bench/run.py --echo-grounding
```

Same queries, same FAQ corpus.

## License

`server/src/llm.py` keeps the Agora recipe's request/SSE contract (MIT). Moss-authored code in this directory is BSD-2-Clause, same as the rest of this repo.
