"""Semantic cache for LLM responses, built on Moss.

A normal cache keys on the exact text of a request, so two ways of asking the
same thing ("what are your hours?" / "when do you open?") miss and you pay the
model twice. A *semantic* cache keys on meaning: embed the question, look up the
nearest one you've already answered, and if it's close enough, return the stored
answer without calling the model.

The whole thing is the SemanticCache class below. The one knob that matters is
the similarity threshold.
"""

import asyncio
import os
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

from moss import MossClient, DocumentInfo, QueryOptions

load_dotenv()

# cosine similarity above which a cached answer is "close enough" to reuse.
# too low -> you answer questions people didn't quite ask; too high -> you miss.
THRESHOLD = 0.92

moss = MossClient(
    project_id=os.getenv("MOSS_PROJECT_ID"),
    project_key=os.getenv("MOSS_PROJECT_KEY"),
)
llm = AsyncOpenAI()


class SemanticCache:
    """A tiny vector index of past questions -> answers, queried by meaning."""

    def __init__(self, index):
        self.index = index

    async def ask(self, question: str) -> tuple[str, bool]:
        # 1. look for the closest question we've already answered
        hit = await self.index.query(question, QueryOptions(top_k=1))
        if hit.docs and hit.docs[0].score >= THRESHOLD:
            return hit.docs[0].metadata["answer"], True  # cache hit — no LLM call

        # 2. miss: ask the model once
        resp = await llm.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}],
        )
        answer = resp.choices[0].message.content

        # 3. remember it so any wording of it is instant next time
        await self.index.add_docs(
            [DocumentInfo(id=question, text=question, metadata={"answer": answer})]
        )
        return answer, False


async def main():
    # a fresh in-memory session index acts as the cache for this run
    index = await moss.session("qa-cache")
    cache = SemanticCache(index)

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
