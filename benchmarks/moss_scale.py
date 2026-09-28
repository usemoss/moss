"""One Moss built-in-model session at N docs: RSS per stage, indexing time, 750-query latency.

Run: MOSS_ENV_FILE=<.env> .venv/bin/python moss_scale.py <n_docs> [docs_per_call]   # default: one call
"""

import asyncio
import json
import sys
import time
import uuid

from moss import DocumentInfo, MutationOptions, QueryOptions

from bench_local import HERE, QUERIES, QUERY_ROUNDS, TOP_K, WARMUP_ROUNDS, report
from moss_persist import client, rss_mb


async def main(n: int, per_call: int) -> None:
    docs = json.loads((HERE / "bench_100k_docs.json").read_text())[:n]
    print(f"  rss start: {rss_mb():.0f} MB")
    session = await client().session(
        f"bench-scale-{uuid.uuid4().hex[:8]}"
    )  # unique, never pushed
    print(f"  rss after session create: {rss_mb():.0f} MB")
    t0 = time.perf_counter()
    for i in range(0, n, per_call):
        await session.add_docs(
            [DocumentInfo(id=d["id"], text=d["text"]) for d in docs[i : i + per_call]],
            MutationOptions(upsert=True),
        )
    add_s = time.perf_counter() - t0
    print(
        f"  add_docs {n} docs in {add_s:.1f}s ({n / add_s:.0f} docs/s); rss after: {rss_mb():.0f} MB"
    )
    opts = QueryOptions(top_k=TOP_K, alpha=1.0)
    lat = []
    for rnd in range(WARMUP_ROUNDS + QUERY_ROUNDS):
        for q in QUERIES:
            t0 = time.perf_counter()
            r = await session.query(q, opts)
            if rnd >= WARMUP_ROUNDS:
                lat.append((time.perf_counter() - t0) * 1000)
            assert len(r.docs) == TOP_K, r
    print(f"  rss after queries: {rss_mb():.0f} MB")
    name = f"moss-scale-{n}" + (f"-per{per_call}" if per_call < n else "")
    report(name, {"end-to-end": lat}, f"add_docs_s={add_s:.1f} docs_per_call={per_call}")


if __name__ == "__main__":
    n = int(sys.argv[1])
    asyncio.run(main(n, int(sys.argv[2]) if len(sys.argv) > 2 else n))
