"""Moss custom-embedding add_docs timing + save_to_disk/load_from_disk round trip at 10k docs.

save_to_disk/load_from_disk live on the private native session (`session._inner`).
Run: MOSS_ENV_FILE=<.env> .venv/bin/python moss_persist.py build          # BENCH_DOCS overrides 10k
     MOSS_ENV_FILE=<.env> .venv/bin/python moss_persist.py restore        # new process, real creds
                          .venv/bin/python moss_persist.py restore-fake   # new process, fake creds
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid

import moss_core
from moss import DocumentInfo, MossClient, MutationOptions, QueryOptions, SessionIndex
from moss_core import PyEmbeddingService

from bench_local import (
    DOC_COUNT,
    HERE,
    QUERIES,
    QUERY_ROUNDS,
    RESULTS,
    TOP_K,
    WARMUP_ROUNDS,
    report,
)

CACHE = HERE / ".moss-sessions"
STATE = RESULTS / "persist_state.json"


def rss_mb() -> float:
    return (
        int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())]))
        / 1024
    )


def client() -> MossClient:
    from dotenv import load_dotenv

    # Without MOSS_ENV_FILE, MOSS_PROJECT_ID/KEY must already be exported.
    if "MOSS_ENV_FILE" in os.environ:
        load_dotenv(os.environ["MOSS_ENV_FILE"], override=True)
    return MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])


def top_ids(session: SessionIndex, qv: dict[str, list[float]]) -> dict[str, list[str]]:
    return {
        q: [d.id for d in session._inner.query(q, TOP_K, qv[q], 1.0, None, None).docs]
        for q in QUERIES
    }


async def build() -> None:
    docs = json.loads((HERE / "bench_100k_docs.json").read_text())[:DOC_COUNT]
    svc = PyEmbeddingService("moss-minilm")
    svc.load_model()
    print(f"  rss after model load: {rss_mb():.0f} MB")

    t0 = time.perf_counter()
    vecs = []
    for i in range(0, len(docs), 256):
        vecs += svc.create_embeddings([d["text"] for d in docs[i : i + 256]])
    embed_s = time.perf_counter() - t0
    print(
        f"  native-embedded {len(vecs)} docs in {embed_s:.1f}s; rss {rss_mb():.0f} MB"
    )

    name = f"bench-persist-{uuid.uuid4().hex[:8]}"  # unique, never pushed
    session = await client().session(name, model_id="custom")
    print(f"  rss after custom session create: {rss_mb():.0f} MB")
    t0 = time.perf_counter()
    await session.add_docs(
        [
            DocumentInfo(id=d["id"], text=d["text"], embedding=v)
            for d, v in zip(docs, vecs)
        ],
        MutationOptions(upsert=True),
    )
    add_s = time.perf_counter() - t0
    print(
        f"  custom add_docs (index only) {len(docs)} docs in {add_s:.1f}s; rss {rss_mb():.0f} MB"
    )

    qv = {q: svc.create_embedding(q) for q in QUERIES}
    public, direct = [], []
    for rnd in range(WARMUP_ROUNDS + QUERY_ROUNDS):
        for q in QUERIES:
            opts = QueryOptions(top_k=TOP_K, alpha=1.0, embedding=qv[q])
            t0 = time.perf_counter()
            r = await session.query(q, opts)
            t1 = time.perf_counter()
            session._inner.query(
                q, TOP_K, qv[q], 1.0, None, None
            )  # same call, no asyncio.to_thread hop
            t2 = time.perf_counter()
            assert len(r.docs) == TOP_K, r
            if rnd >= WARMUP_ROUNDS:
                public.append((t1 - t0) * 1000)
                direct.append((t2 - t1) * 1000)
    report(
        "moss-search-only",
        {"public query() (to_thread)": public, "_inner.query (direct)": direct},
        f"embed_s={embed_s:.1f} add_docs_s={add_s:.1f}",
    )

    ids = top_ids(session, qv)
    t0 = time.perf_counter()
    session._inner.save_to_disk(str(CACHE))
    save_s = time.perf_counter() - t0
    size = subprocess.check_output(["du", "-sh", str(CACHE / name)]).decode().split()[0]
    print(f"  save_to_disk {save_s:.2f}s, {size} at {CACHE / name}")
    STATE.write_text(
        json.dumps(
            {
                "name": name,
                "n": len(docs),
                "ids": ids,
                "qv": qv,
                "add_s": add_s,
                "embed_s": embed_s,
            }
        )
    )


async def restore(fake: bool) -> None:
    state = json.loads(STATE.read_text())
    name = state["name"]
    if (
        fake
    ):  # bypass MossClient: build the native session directly with bogus credentials
        try:
            inner = moss_core.SessionIndex(name, "custom", "fake-project", "fake-key")
        except ValueError as e:
            if "Authentication failed" not in str(e):
                raise
            print(
                f"  expected: native session rejects fake credentials, so no offline restore ({e})"
            )
            return
        session = SessionIndex(name, "custom", inner)
    else:
        session = await client().session(name, model_id="custom")
    print(
        f"  session created (fake_creds={fake}), doc_count before load: {session.doc_count}"
    )
    t0 = time.perf_counter()
    n = session._inner.load_from_disk(str(CACHE))
    load_s = time.perf_counter() - t0
    ids = top_ids(session, state["qv"])
    same = sum(ids[q] == state["ids"][q] for q in QUERIES)
    print(
        f"  load_from_disk -> {n} docs in {load_s:.2f}s (rebuild was {state['add_s']:.1f}s index "
        f"+ {state['embed_s']:.1f}s embed); top-{TOP_K} identical for {same}/{len(QUERIES)} queries; "
        f"rss {rss_mb():.0f} MB"
    )
    assert n == state["n"] and same == len(QUERIES)


if __name__ == "__main__":
    mode = sys.argv[1]
    asyncio.run(build() if mode == "build" else restore(fake=mode == "restore-fake"))
