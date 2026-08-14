# Offline Moss bench

Gold-phrase table over the 10 FAQs in `../data/knowledge.jsonl`. No mic, no Agora, no Deepgram.

Three arms per query:

| Arm | What happens |
| --- | --- |
| `ambient` | always search, answer is the retrieved block |
| `tool` | always search (`--echo-grounding` has no LLM to decide), answer is the block |
| `no-moss` | empty answer |

`faithful` means the gold phrase is in the answer. `hit` means it is in the retrieved block.

```bash
# from apps/ten-moss
export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=ten-moss-demo
python create_index.py
python bench/run.py --echo-grounding
```

No Moss keys? The script still prints the table by pairing each query with its FAQ. `moss_retrieval_ms` is then `n/a`.

Exact query strings: `queries.jsonl`.
