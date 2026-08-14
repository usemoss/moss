# Offline Moss bench (ambient / tool / no-Moss)

Gold-phrase table over the 10 FAQs in `../data/knowledge.jsonl`. No mic, no Agora, no Deepgram.

## What it measures

Per query, three arms:

| Arm | What the "model" sees | When Moss runs |
| --- | --- | --- |
| `ambient` | retrieved block (always searched) | every query |
| `tool` | retrieved block if the tool ran | `--echo-grounding` always calls `search_knowledge_base` (no LLM to decide) |
| `no-moss` | empty context | never |

`--echo-grounding` is the zero-LLM smoke: the "answer" is the retrieved block, so `faithful` equals "gold phrase is in the block." That proves retrieval without an LLM key.

| Metric | Meaning |
| --- | --- |
| `moss_retrieval_ms` | SDK `SearchResult.time_taken_ms` (n/a without a Moss session) |
| `moss_wall_ms` | `perf_counter` around `query_context` |
| `hit` | retrieved block contains a gold phrase (or doc id `kb-N`) |
| `faithful` | answer contains a gold phrase |
| `tool_called` | tool arm only |

## Run

```bash
# From apps/ten-moss
export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=ten-moss-demo
python create_index.py
python bench/run.py --echo-grounding
```

The script still prints the markdown table if Moss credentials are missing: it falls back to a local substring lookup over `data/knowledge.jsonl`. SDK timings are then `n/a`. That path is for reading the table format, not for publishing latency.

Optional: `python bench/run.py --echo-grounding --json /tmp/bench.json`

## Gold queries

Exact strings live in `queries.jsonl`. They match the 10 FAQ lines.

## Tool-arm stub

`--echo-grounding` has no chat model, so the tool arm **always** invokes `search_knowledge_base`. A live LLM arm (model decides) is residual polish, not this slice.
