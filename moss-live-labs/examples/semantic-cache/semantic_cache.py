"""Semantic cache for LLM responses, built on Moss.

A normal cache keys on the exact text of a request, so two ways of asking the
same thing ("what are your hours?" / "when do you open?") miss and you pay the
model twice. A *semantic* cache keys on meaning: embed the question, look up the
nearest one you've already answered, and if it's close enough, return the stored
answer without calling the model.

The core is the SemanticCache class below (the `ask` method is the whole idea).
The one knob that matters is the similarity threshold.
"""

import asyncio
import os
import sys
import time
import uuid

from dotenv import load_dotenv
from openai import AsyncOpenAI

from moss import MossClient, DocumentInfo, QueryOptions

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        sys.exit(f"Missing {name}. Copy .env.example to .env and fill in your keys.")
    return value


# fail fast with a clear message if credentials are missing
MOSS_PROJECT_ID = _require("MOSS_PROJECT_ID")
MOSS_PROJECT_KEY = _require("MOSS_PROJECT_KEY")
_require("OPENAI_API_KEY")  # read by AsyncOpenAI from the environment

# semantic similarity above which a cached answer is "close enough" to reuse.
# too low -> you answer questions people didn't quite ask; too high -> you miss.
THRESHOLD = 0.92

moss = MossClient(project_id=MOSS_PROJECT_ID, project_key=MOSS_PROJECT_KEY)
llm = AsyncOpenAI()


class SemanticCache:
    """A small store of past questions -> answers, looked up by meaning."""

    def __init__(self, store):
        self.store = store

    async def ask(self, question: str) -> tuple[str, bool]:
        # 1. look for the closest question we've already answered.
        #    alpha=1.0 -> pure semantic (embedding) match, so the score reflects
        #    meaning rather than keyword overlap.
        hit = await self.store.query(question, QueryOptions(top_k=1, alpha=1.0))
        if hit.docs and hit.docs[0].score >= THRESHOLD:
            answer = (hit.docs[0].metadata or {}).get("answer")
            if answer is not None:
                return answer, True  # cache hit — no LLM call

        # 2. miss: ask the model once
        resp = await llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}],
        )
        answer = resp.choices[0].message.content or ""

        # 3. remember it so any wording of it is instant next time
        await self.store.add_docs(
            [DocumentInfo(id=question, text=question, metadata={"answer": answer})]
        )
        return answer, False


async def main():
    # A Moss session is the cache store. We use a unique name per run so the demo
    # always starts empty and shows a clean MISS -> HIT (a session auto-loads an
    # existing cloud index of the same name, which would otherwise make the first
    # question a HIT). In production, use a stable name and call
    # `await store.push_index()` to persist the cache across runs and processes.
    store = await moss.session(index_name=f"qa-cache-demo-{uuid.uuid4().hex[:8]}")
    cache = SemanticCache(store)

    # the 2nd question means the same as the 1st, phrased differently -> cache hit
    questions = [
        "What are your opening hours?",
        "when do you open?",
        "How do I reset my password?",
    ]
    for q in questions:
        t = time.perf_counter()
        answer, hit = await cache.ask(q)
        ms = (time.perf_counter() - t) * 1000
        tag = "HIT " if hit else "MISS"
        print(f"[{tag} {ms:7.1f} ms]  {q}\n   -> {answer.strip()[:90]}\n")


if __name__ == "__main__":
    asyncio.run(main())
