"""Where does Moss built-in ingest memory go? 1,000 paper chunks, one session per process.

RSS after: session create, ingest, delete of all docs, re-ingest of the same docs, session drop.
Re-ingest not growing RSS => memory is reused (arena/cache), not leaked per call.
Run: MOSS_ENV_FILE=<.env> .venv/bin/python moss_mem.py <docs_per_call> [n_docs]   # 1000 | 100 | 1
"""

import asyncio
import gc
import json
import resource
import sys
import time
import uuid

from moss import DocumentInfo, MutationOptions

from doc_chunk_eval import OUT
from moss_persist import client, rss_mb


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


async def main(per_call: int, n: int) -> None:
    docs = [
        DocumentInfo(id=d["id"], text=d["text"])
        for d in json.loads((OUT / "builtin-paper-docs.json").read_text())[:n]
    ]
    log = {"docs_per_call": per_call, "n_docs": len(docs), "start": rss_mb()}
    session = await client().session(f"docmem-{uuid.uuid4().hex[:8]}")  # never pushed
    log["session created"] = rss_mb()

    async def ingest(s) -> float:
        t0 = time.perf_counter()
        for i in range(0, len(docs), per_call):
            await s.add_docs(docs[i : i + per_call], MutationOptions(upsert=True))
        return time.perf_counter() - t0

    log["ingest_s"] = round(await ingest(session), 2)
    log["after ingest"], log["peak after ingest"] = rss_mb(), peak_mb()
    await session.delete_docs([d.id for d in docs])
    gc.collect()
    log["after delete all (doc_count=%d)" % session.doc_count] = rss_mb()
    log["re-ingest_s"] = round(await ingest(session), 2)
    log["after re-ingest"], log["peak after re-ingest"] = rss_mb(), peak_mb()
    del session
    gc.collect()
    time.sleep(2)
    log["after session drop"] = rss_mb()
    line = json.dumps(
        {
            k: (round(v) if isinstance(v, float) and "_s" not in k else v)
            for k, v in log.items()
        }
    )
    print(line)
    with open(OUT / "moss_mem.jsonl", "a") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1_000))
