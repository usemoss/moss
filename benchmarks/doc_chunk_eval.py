"""Research-paper chunks vs small benchmark docs: Moss vs Chroma with precomputed qwen3 embeddings.

Needs Ollama with qwen3-embedding:4b-q8_0 and the arXiv PDFs (./run_local.sh fetch-arxiv).
Steps (each its own process):
  .venv/bin/python doc_chunk_eval.py prep                 # chunk PDFs, embed docs+queries via Ollama, save to disk
  .venv/bin/python doc_chunk_eval.py query-embed          # query-embedding latency + model footprint
  MOSS_ENV_FILE=<.env> .venv/bin/python doc_chunk_eval.py run moss|chroma paper|small
"""

import asyncio
import glob
import json
import re
import subprocess
import sys
import threading
import time
import uuid

import numpy as np
import requests
from tokenizers import Tokenizer

from bench_local import HERE, QUERY_ROUNDS, RESULTS, TOP_K, WARMUP_ROUNDS, report
from moss_persist import rss_mb

OUT = RESULTS / "docchunk"
# arxiv.sha256 lists the PDFs in corpus order; this benchmark uses the first two.
ARXIV = [
    HERE / "data/arxiv" / line.split()[1]
    for line in (HERE / "arxiv.sha256").read_text().splitlines()
]
PDFS = ARXIV[:2]
OLLAMA = "http://localhost:11434"
MODEL = "qwen3-embedding:4b-q8_0"
MAX_TOKENS = 512  # Moss manifest maximumTokens; local Chroma has no per-doc limit
BUDGET = MAX_TOKENS - 1 - 2  # strictly below 512 including [CLS]/[SEP]
OVERLAP = 64  # tokens (~12.5%), whole trailing sentences, within a section
INSTRUCT = "Instruct: Given a question about a research paper, retrieve relevant passages that answer the question\nQuery:"
QUERIES = [
    "What is the verifier tax in tool-using LLM agents?",
    "How does runtime safety enforcement affect task success on τ-bench?",
    "What are integrity leaks where agents hallucinate user identifiers?",
    "How often do agents recover after a blocked action?",
    "What is the difference between safe success rate and unsafe success rate?",
    "Which interaction horizons were found for GPT-OSS-20B and GLM-4-9B?",
    "How does the Triad-Safety architecture mediate tool calls?",
    "How was the user simulator configured in the experiments?",
    "What is performative chain-of-thought in reasoning models?",
    "How do attention probes decode a model's final answer from activations?",
    "How does forced answering compare with a chain-of-thought monitor?",
    "Why do easy MMLU questions show more performative reasoning than GPQA-Diamond?",
    "Do backtracking and aha moments indicate genuine uncertainty?",
    "How much does probe-guided early exit reduce token usage?",
    "How does model size affect performative reasoning trends?",
]
HEADING = re.compile(r"^(\d+(\.\d+)*\.?|[A-Z](\.\d+)*\.)\s+[A-Z].{2,80}$")


def tokenizer() -> Tokenizer:
    tok = Tokenizer.from_file(
        glob.glob(
            str(
                HERE
                / ".fastembed_cache/models--qdrant--all-MiniLM-L6-v2-onnx/snapshots/*/tokenizer.json"
            )
        )[0]
    )
    tok.no_padding()
    tok.no_truncation()
    return tok


def chunk_text(text: str, tok: Tokenizer, max_tokens: int = MAX_TOKENS, overlap: int = OVERLAP) -> list[str]:
    """Section-aware greedy sentence packing, strictly under max_tokens incl. [CLS]/[SEP], with overlap-token sentence carry-over."""
    budget = max_tokens - 1 - 2
    text = re.sub(r"-\n(?=[a-z])", "", text)  # rejoin hyphenated line breaks
    sections, cur = [], []
    for line in text.split("\n"):
        if HEADING.match(line.strip()) and cur:
            sections.append(" ".join(cur))
            cur = []
        cur.append(line.strip())
    sections.append(" ".join(cur))

    def ntok(s: str) -> int:
        return len(tok.encode(s, add_special_tokens=False).ids)

    merged: list[str] = []  # fold heading-only sections (e.g. '3 Methods' directly above '3.1 ...') into the next one
    for sec in sections:
        if merged and ntok(merged[-1]) < 32 and not re.search(r"[.!?]\s*$", merged[-1]):
            merged[-1] = f"{merged[-1]} {sec}"
        else:
            merged.append(sec)

    chunks = []
    for sec in merged:
        sents = []
        for s in re.split(
            r"(?<=[.!?])\s+(?=[A-Z(\[])", re.sub(r"\s+", " ", sec).strip()
        ):
            if ntok(s) <= budget:
                sents.append((s, ntok(s)))
                continue
            piece: list[str] = []  # hard-split over-budget sentences on word boundaries
            for w in s.split(" "):
                if piece and ntok(" ".join(piece + [w])) > budget:
                    sents.append((" ".join(piece), ntok(" ".join(piece))))
                    piece = []
                piece.append(w)
            if piece:
                sents.append((" ".join(piece), ntok(" ".join(piece))))
        buf: list[tuple[str, int]] = []
        for s, n in sents:
            if buf and sum(x[1] for x in buf) + n > budget:
                chunks.append(" ".join(x[0] for x in buf))
                carry: list[tuple[str, int]] = []
                for x in reversed(buf):
                    if sum(c[1] for c in carry) + x[1] > overlap:
                        break
                    carry.insert(0, x)
                buf = carry if sum(c[1] for c in carry) + n <= budget else []
            buf.append((s, n))
        if buf:
            chunks.append(" ".join(x[0] for x in buf))
    chunks = [c for c in chunks if c.strip()]
    for c in (
        chunks
    ):  # re-encode the joined text: the limit must hold on what is actually embedded
        assert len(tok.encode(c).ids) < max_tokens, (len(tok.encode(c).ids), c[:80])
    return chunks


def ollama_embed(texts: list[str]) -> dict:
    r = requests.post(
        f"{OLLAMA}/api/embed", json={"model": MODEL, "input": texts}, timeout=600
    )
    r.raise_for_status()
    return r.json()


def unload() -> None:
    requests.post(
        f"{OLLAMA}/api/generate", json={"model": MODEL, "keep_alive": 0}, timeout=60
    ).raise_for_status()


def embed_corpus(name: str, texts: list[str], batch: int = 16) -> np.ndarray:
    vecs, tokens = [], 0
    t0 = time.perf_counter()
    for i in range(0, len(texts), batch):
        d = ollama_embed(texts[i : i + batch])
        vecs += d["embeddings"]
        tokens += d["prompt_eval_count"]
    s = time.perf_counter() - t0
    line = f"  {name}: embedded {len(texts)} docs ({tokens} qwen3 tokens) in {s:.2f}s -> {len(texts) / s:.1f} docs/s, {tokens / s:.0f} tokens/s (batch {batch}, model already loaded)"
    print(line)
    (OUT / f"throughput-{name}.txt").write_text(line + "\n")
    v = np.asarray(vecs, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def prep() -> None:
    from pypdf import PdfReader

    OUT.mkdir(parents=True, exist_ok=True)
    tok = tokenizer()
    paper = []
    for f in PDFS:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(f).pages)
        paper += [
            {"id": f"{f.stem}-{i}", "text": c}
            for i, c in enumerate(chunk_text(text, tok))
        ]
    n = len(paper)
    small = json.loads((HERE / "bench_100k_docs.json").read_text())[:n]
    for name, docs in (("paper", paper), ("small", small)):
        lens = [len(tok.encode(d["text"]).ids) for d in docs]
        print(
            f"  {name}: {len(docs)} docs, MiniLM tokens incl. specials min/median/max = {min(lens)}/{int(np.median(lens))}/{max(lens)}, chars total {sum(len(d['text']) for d in docs)}"
        )
        (OUT / f"{name}-docs.json").write_text(json.dumps(docs))

    t0 = time.perf_counter()
    d = ollama_embed(["warmup"])  # cold load, excluded from throughput
    print(
        f"  cold model load + first embed: {time.perf_counter() - t0:.2f}s (load_duration {d['load_duration'] / 1e9:.2f}s)"
    )
    for name in ("paper", "small"):
        docs = json.loads((OUT / f"{name}-docs.json").read_text())
        np.save(OUT / f"{name}-vecs.npy", embed_corpus(name, [x["text"] for x in docs]))
    qv = np.asarray(
        ollama_embed([INSTRUCT + q for q in QUERIES])["embeddings"], dtype=np.float32
    )
    np.save(OUT / "query-vecs.npy", qv / np.linalg.norm(qv, axis=1, keepdims=True))
    unload()
    print("  model unloaded")


def query_embed() -> None:
    """Per-query embed latency (HTTP round trip included) and the model's memory footprint."""
    OUT.mkdir(parents=True, exist_ok=True)
    ollama_embed(["warmup"])
    ps = requests.get(f"{OLLAMA}/api/ps", timeout=10).json()["models"][0]
    pid = (
        subprocess.check_output(["pgrep", "-f", "llama-server.*--embedding"])
        .split()[0]
        .decode()
    )
    peak = [0.0]
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            out = subprocess.run(
                ["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True
            ).stdout.strip()
            if out:
                peak[0] = max(peak[0], int(out) / 1024)
            time.sleep(0.2)

    threading.Thread(target=sample, daemon=True).start()
    lat = []
    for rnd in range(WARMUP_ROUNDS + QUERY_ROUNDS):
        for q in QUERIES:
            t0 = time.perf_counter()
            ollama_embed([INSTRUCT + q])
            if rnd >= WARMUP_ROUNDS:
                lat.append((time.perf_counter() - t0) * 1000)
    stop.set()
    extra = (
        f"ollama /api/ps size={ps['size'] / 2**30:.2f} GiB size_vram={ps['size_vram'] / 2**30:.2f} GiB "
        f"context_length={ps.get('context_length')}; llama-server pid {pid} peak RSS {peak[0]:.0f} MB"
    )
    report("docchunk-query-embed", {"qwen3 query embed (HTTP)": lat}, extra)
    unload()


def run(system: str, corpus: str) -> None:
    docs = json.loads((OUT / f"{corpus}-docs.json").read_text())
    vecs = np.load(OUT / f"{corpus}-vecs.npy").tolist()
    qv = np.load(OUT / "query-vecs.npy").tolist()
    stages = {"before build": rss_mb()}
    if system == "moss":
        from moss import DocumentInfo, MutationOptions, QueryOptions

        from moss_persist import client

        loop = asyncio.new_event_loop()  # one loop for session, build and every query

        session = loop.run_until_complete(
            client().session(f"docchunk-{uuid.uuid4().hex[:8]}", model_id="custom")
        )  # never pushed
        t0 = time.perf_counter()
        loop.run_until_complete(
            session.add_docs(
                [
                    DocumentInfo(id=d["id"], text=d["text"], embedding=v)
                    for d, v in zip(docs, vecs)
                ],
                MutationOptions(upsert=True),
            )
        )
        build_s = time.perf_counter() - t0

        def search(i: int) -> list[str]:
            opts = QueryOptions(top_k=TOP_K, alpha=1.0, embedding=qv[i])
            return [
                x.id
                for x in loop.run_until_complete(session.query(QUERIES[i], opts)).docs
            ]
    else:
        import chromadb
        from chromadb.config import Settings

        col = chromadb.EphemeralClient(
            Settings(anonymized_telemetry=False)
        ).create_collection("bench", configuration={"hnsw": {"space": "cosine"}})
        t0 = time.perf_counter()
        for i in range(0, len(docs), 250):
            col.add(
                ids=[d["id"] for d in docs[i : i + 250]],
                embeddings=vecs[i : i + 250],
                documents=[d["text"] for d in docs[i : i + 250]],
            )
        build_s = time.perf_counter() - t0

        def search(i: int) -> list[str]:
            return col.query(query_embeddings=[qv[i]], n_results=TOP_K)["ids"][0]

    stages["after build"] = rss_mb()
    lat = []
    for rnd in range(WARMUP_ROUNDS + QUERY_ROUNDS):
        for i in range(len(QUERIES)):
            t0 = time.perf_counter()
            ids = search(i)
            if rnd >= WARMUP_ROUNDS:
                lat.append((time.perf_counter() - t0) * 1000)
            assert len(ids) == TOP_K, ids
    stages["after queries"] = rss_mb()
    (OUT / f"top5-{system}-{corpus}.json").write_text(
        json.dumps({q: search(i) for i, q in enumerate(QUERIES)})
    )
    rss = " ".join(f"{k}={v:.0f}MB" for k, v in stages.items())
    report(
        f"docchunk-{system}-{corpus}",
        {"search-only (precomputed query vec)": lat},
        f"n={len(docs)} build_s={build_s:.3f} {rss}",
    )


if __name__ == "__main__":
    {"prep": prep, "query-embed": query_embed}.get(
        sys.argv[1], lambda: run(sys.argv[2], sys.argv[3])
    )()
