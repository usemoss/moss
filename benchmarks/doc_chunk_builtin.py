"""Built-in ingestion path on research-paper chunks: Moss (moss-minilm) vs Chroma (DefaultEmbeddingFunction).

Both embed inside the DB on add and on query (same MiniLM-L6-v2 weights). Chunks < 256 tokens incl.
[CLS]/[SEP]: the lower of Moss's 512 and Chroma's default embedder (truncates/pads to 256).
  .venv/bin/python doc_chunk_builtin.py prep
  MOSS_ENV_FILE=<.env> .venv/bin/python doc_chunk_builtin.py ramp [max_n]  # all runs, with stop rule
  MOSS_ENV_FILE=<.env> .venv/bin/python doc_chunk_builtin.py run moss|chroma|chroma-reuse|chroma-unpadded paper|small <n>
"""

import asyncio
import json
import re
import subprocess
import sys
import time
import uuid

import numpy as np

from bench_local import (
    HERE,
    MEM_LIMIT_MB,
    QUERY_ROUNDS,
    TOP_K,
    WARMUP_ROUNDS,
    report,
    unpadded_chroma_ef,
)
from doc_chunk_eval import ARXIV, OUT, QUERIES, chunk_text, tokenizer
from moss_persist import rss_mb

MAX_TOKENS, OVERLAP, N = 256, 32, 1_000
CHROMA_CACHE = HERE / ".chroma_cache/onnx_models/all-MiniLM-L6-v2"


def prep() -> None:
    from pypdf import PdfReader

    OUT.mkdir(parents=True, exist_ok=True)
    tok = tokenizer()
    paper = []
    for f in ARXIV:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(f).pages)
        paper += [
            {"id": f"{f.stem}-{i}", "text": c}
            for i, c in enumerate(chunk_text(text, tok, MAX_TOKENS, OVERLAP))
        ]
    paper = paper[:N]
    small = json.loads((HERE / "bench_100k_docs.json").read_text())[:N]
    for name, docs in (("paper", paper), ("small", small)):
        lens = [len(tok.encode(d["text"]).ids) for d in docs]
        print(
            f"  {name}: {len(docs)} docs from {len({d['id'].rsplit('-', 1)[0] for d in docs})} sources; tokens incl. specials min/median/max {min(lens)}/{int(np.median(lens))}/{max(lens)}, total {sum(lens)}"
        )
        (OUT / f"builtin-{name}-docs.json").write_text(json.dumps(docs))


def run(system: str, corpus: str, n: int) -> None:
    docs = json.loads((OUT / f"builtin-{corpus}-docs.json").read_text())[:n]
    tokens = sum(len(tokenizer().encode(d["text"]).ids) for d in docs)
    stages = {"start": rss_mb()}
    if system == "moss":
        from moss import DocumentInfo, MutationOptions, QueryOptions

        from moss_persist import client

        loop = asyncio.new_event_loop()
        session = loop.run_until_complete(
            client().session(f"docbuiltin-{uuid.uuid4().hex[:8]}")
        )  # never pushed
        stages["model loaded"] = rss_mb()
        t0 = time.perf_counter()
        loop.run_until_complete(
            session.add_docs(
                [DocumentInfo(id=d["id"], text=d["text"]) for d in docs],
                MutationOptions(upsert=True),
            )
        )
        ingest_s = time.perf_counter() - t0
        opts = QueryOptions(top_k=TOP_K, alpha=1.0)

        def search(q: str) -> list[str]:
            return [x.id for x in loop.run_until_complete(session.query(q, opts)).docs]
    else:
        import chromadb
        from chromadb.config import Settings
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )

        ONNXMiniLM_L6_V2.DOWNLOAD_PATH = (
            CHROMA_CACHE  # keep the model download inside the project
        )
        col = chromadb.EphemeralClient(
            Settings(anonymized_telemetry=False)
        ).create_collection(
            "bench",
            # DefaultEmbeddingFunction builds a new ONNX session per call (~31 ms); chroma-reuse keeps one instance
            embedding_function={"chroma-reuse": ONNXMiniLM_L6_V2, "chroma-unpadded": unpadded_chroma_ef}.get(system, DefaultEmbeddingFunction)(),
            configuration={"hnsw": {"space": "cosine"}},
        )
        col.query(
            query_texts=["warm up model load"], n_results=1
        )  # load the ONNX model before timing ingest
        stages["model loaded"] = rss_mb()
        t0 = time.perf_counter()
        for i in range(0, len(docs), 250):
            col.add(
                ids=[d["id"] for d in docs[i : i + 250]],
                documents=[d["text"] for d in docs[i : i + 250]],
            )
        ingest_s = time.perf_counter() - t0

        def search(q: str) -> list[str]:
            return col.query(query_texts=[q], n_results=TOP_K)["ids"][0]

    stages["after ingest"] = rss_mb()
    lat = []
    for rnd in range(WARMUP_ROUNDS + QUERY_ROUNDS):
        for q in QUERIES:
            t0 = time.perf_counter()
            ids = search(q)
            if rnd >= WARMUP_ROUNDS:
                lat.append((time.perf_counter() - t0) * 1000)
            assert len(ids) == TOP_K, ids
    stages["after queries"] = rss_mb()
    (OUT / f"builtin-top5-{system}-{corpus}-{n}.json").write_text(
        json.dumps({q: search(q) for q in QUERIES})
    )
    rss = " ".join(f"{k}={v:.0f}MB" for k, v in stages.items())
    report(
        f"docbuiltin-{system}-{corpus}-{n}",
        {"end-to-end (embed + search)": lat},
        f"n={n} tokens={tokens} ingest_s={ingest_s:.2f} ({n / ingest_s:.0f} docs/s, {tokens / ingest_s:.0f} tok/s) {rss}",
    )


def ramp(max_n: int) -> None:
    """Paper chunks 125 -> 1000 per system, then 1000 small docs; halt on a projected peak > MEM_LIMIT_MB."""
    steps = [
        (s, "paper", n) for n in (125, 250, 500, 1000) for s in ("moss", "chroma")
    ] + [(s, "small", N) for s in ("moss", "chroma")]
    steps = [x for x in steps if x[2] <= max_n]
    peaks: dict[str, list[tuple[int, float]]] = {}
    for i, (system, corpus, n) in enumerate(steps):
        log = OUT / f"docbuiltin-{system}-{corpus}-{n}.log"
        rc = subprocess.call(
            [
                str(HERE / "watchdog.sh"),
                str(log),
                str(HERE / ".venv/bin/python"),
                "doc_chunk_builtin.py",
                "run",
                system,
                corpus,
                str(n),
            ],
            cwd=HERE,
        )
        text = log.read_text()
        print(text.strip(), flush=True)
        if rc != 0:
            print(f"HALT: {system} {corpus} {n} exited rc={rc}")
            return
        peak = max(
            float(re.search(r"peak RSS (\d+) MB", text).group(1)),
            float(re.search(r"peak_rss_mb=(\d+)", text).group(1)),
        )
        if corpus == "paper":
            peaks.setdefault(system, []).append((n, peak))
            pts = peaks[system]
            nxt = next(
                (m for s, c, m in steps[i + 1 :] if s == system and c == "paper"), None
            )
            if len(pts) >= 2 and nxt:
                (n1, p1), (n2, p2) = pts[-2:]
                projected = p2 + (p2 - p1) / (n2 - n1) * (nxt - n2)
                print(
                    f"  {system}: projected peak at {nxt} = {projected:.0f} MB",
                    flush=True,
                )
                if projected > MEM_LIMIT_MB:
                    print(f"HALT: {system} projection {projected:.0f} MB > {MEM_LIMIT_MB:.0f} MB")
                    return


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep()
    elif cmd == "ramp":
        ramp(int(sys.argv[2]) if len(sys.argv) > 2 else N)
    else:
        run(sys.argv[2], sys.argv[3], int(sys.argv[4]))
