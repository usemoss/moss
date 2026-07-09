# Semantic cache for LLM responses

Cache LLM answers by **meaning**, not by exact text.

A normal cache keys on the literal request string, so two phrasings of the same
question miss:

```
"what are your hours?"   ->  MISS  ->  calls the model
"when do you open?"      ->  MISS  ->  calls the model again   (paid twice)
```

A semantic cache embeds the question and looks up the nearest one it has already
answered. If it's close enough, it returns the stored answer with no model call.
Repeat questions come back in single-digit-millisecond retrieval, on-device.

```
"what are your hours?"   ->  MISS  ->  calls the model, stores the answer
"when do you open?"      ->  HIT   ->  returns the stored answer, no model call
```

## How it works

Here's the idea, simplified (the runnable `ask()` in
[`semantic_cache.py`](./semantic_cache.py) also returns whether it was a hit and
prints timing):

```python
async def ask(self, question):
    hit = await self.store.query(question, QueryOptions(top_k=1))
    if hit.docs and hit.docs[0].score >= THRESHOLD:   # close enough in meaning?
        return hit.docs[0].metadata["answer"]           # cache hit — no LLM call
    answer = await call_the_model(question)             # miss — ask once
    await self.store.add_docs(
        [DocumentInfo(id=question, text=question, metadata={"answer": answer})])
    return answer
```

Moss keys the cache on the question's embedding and serves the nearest match
in <10 ms locally, so the lookup is far cheaper than the model call it avoids.
The one knob that matters is `THRESHOLD` (cosine similarity): too low and you
answer questions people didn't quite ask; too high and you miss obvious matches.

## What you need

- A [Moss](https://moss.dev) account (`MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY`)
- An OpenAI key (the example uses `gpt-4o-mini` as the model being cached)
- Python 3.10+

## Run

```bash
uv sync                       # or: pip install moss openai python-dotenv
cp .env.example .env          # fill in your keys
python semantic_cache.py
```

Expected: the first question is a `MISS` (calls the model), the paraphrased
second question is a `HIT` (returns instantly, no model call).

## Resources

- [Docs](https://docs.moss.dev)
- [GitHub](https://github.com/usemoss/moss)
