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
# run.py loads ../.env before reading MOSS_*
python create_index.py
python bench/run.py --echo-grounding
```

`hit` is a gold phrase in the retrieved text, not a matching `doc_id`. Refunds and shipping use distinct gold phrases.

No Moss keys? The script still prints the table by pairing each query with its FAQ. `moss_retrieval_ms` is then `n/a`.

Exact query strings: `queries.jsonl`.
