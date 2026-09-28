"""Local (in-process) end-to-end latency on 10k docs, all embedding on-device.

Competitors embed with fastembed all-MiniLM-L6-v2; Moss uses its built-in moss-minilm.
Same queries/protocol as the cloud benchmarks (3 warmup rounds, 50 x 15 measured, top_k=5).

Run one DB per process: .venv/bin/python bench_local.py lancedb|lancedb-hnsw|chroma|chroma-unpadded|qdrant|moss
Moss needs MOSS_ENV_FILE=<path to .env with MOSS_PROJECT_ID/KEY> (or both variables exported).
BENCH_DOCS overrides the doc count (smoke tests); BENCH_RESULTS overrides the output directory.
"""

import asyncio
import json
import os
import platform
import resource
import shutil
import sys
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from stats import BenchmarkResult, Timer

HERE = Path(__file__).parent
RESULTS = Path(os.environ.get("BENCH_RESULTS", HERE / "results"))
DOC_COUNT = int(os.environ.get("BENCH_DOCS", 10_000))
# Ramp stop rules halt when projected peak RSS exceeds 75% of this machine's RAM.
MEM_LIMIT_MB = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") * 0.75 / 2**20
TOP_K = 5
WARMUP_ROUNDS = 3
QUERY_ROUNDS = 50
# Copied from corpus.py, whose import runs load_dotenv() and walks up to unrelated .env files.
QUERIES = [
    "neural network training data",
    "anomaly detection patterns",
    "computer vision image processing",
    "natural language processing",
    "reinforcement learning rewards",
    "transfer learning pretrained models",
    "distributed computing systems",
    "cryptographic data encryption",
    "database indexing performance",
    "knowledge graph entities",
    "generative adversarial networks",
    "attention mechanism transformers",
    "dimensionality reduction compression",
    "federated learning privacy",
    "stream processing pipelines",
]
PKG = {
    "lancedb": "lancedb",
    "lancedb-hnsw": "lancedb",
    "chroma": "chromadb",
    "chroma-unpadded": "chromadb",
    "qdrant": "qdrant-client",
    "moss": "moss",
}


def report(name: str, series: dict[str, list[float]], extra: str = "") -> None:
    peak_mb = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
    )  # bytes on macOS
    lines = [
        f"== {name}  ({platform.machine()}, {os.cpu_count()} cores, peak RSS {peak_mb:.0f} MB) {extra}"
    ]
    lines += [BenchmarkResult(f"{name} [{k}]", v).summary() for k, v in series.items()]
    text = "\n".join(lines)
    print(text)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.txt").write_text(text + "\n")
    (RESULTS / f"{name}.json").write_text(json.dumps(series))


def measure(embed, search) -> dict[str, list[float]]:
    """embed(q) -> vector; search(vector) -> hits. Times both together and search alone."""
    with Timer() as t:
        search(embed(QUERIES[0]))
    print(f"  cold query: {t.elapsed_ms:.3f} ms")
    for _ in range(WARMUP_ROUNDS):
        for q in QUERIES:
            search(embed(q))
    e2e, search_only = [], []
    for _ in range(QUERY_ROUNDS):
        for q in QUERIES:
            t0 = time.perf_counter()
            v = embed(q)
            t1 = time.perf_counter()
            hits = search(v)
            t2 = time.perf_counter()
            assert len(hits) == TOP_K, hits
            e2e.append((t2 - t0) * 1000)
            search_only.append((t2 - t1) * 1000)
    return {"end-to-end": e2e, "search-only": search_only}


def unpadded_chroma_ef():
    """Chroma's own MiniLM embedder; single inputs (queries) skip the fixed 256-token padding.

    Batches keep padding because ONNXMiniLM_L6_V2 encodes docs one by one and stacks them;
    with the attention mask, padding does not change the vectors (min cosine 0.99999994).
    """
    from chromadb.utils.embedding_functions import EmbeddingFunction
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    ONNXMiniLM_L6_V2.DOWNLOAD_PATH = HERE / ".chroma_cache/onnx_models/all-MiniLM-L6-v2"

    class UnpaddedQueryEF(EmbeddingFunction):
        def __init__(self) -> None:
            self.pad, self.nopad = ONNXMiniLM_L6_V2(), ONNXMiniLM_L6_V2()
            # The first call downloads the model files that .tokenizer reads.
            self.nopad(["warm up"])
            self.nopad.tokenizer.no_padding()

        def __call__(self, input):
            return (self.nopad if len(input) == 1 else self.pad)(input)

    return UnpaddedQueryEF()


def run_competitor(db: str, docs: list[dict]) -> None:
    from fastembed import TextEmbedding

    model = TextEmbedding(
        "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir=str(HERE / ".fastembed_cache"),
    )
    texts = [d["text"] for d in docs]
    with Timer() as t:
        vecs = [v.tolist() for v in model.embed(texts)]
    embed_s = t.elapsed_ms / 1000

    def embed(q: str) -> list[float]:
        return next(iter(model.embed([q]))).tolist()

    with Timer() as t:
        if db.startswith("lancedb"):
            import lancedb
            from lancedb.index import HnswSq

            path = HERE / ".lancedb" / uuid.uuid4().hex[:8]
            table = lancedb.connect(path).create_table(
                "bench",
                [
                    {"id": d["id"], "text": d["text"], "vector": v}
                    for d, v in zip(docs, vecs)
                ],
            )
            if db == "lancedb-hnsw":
                # num_partitions=1: the HnswSq docstring recommends few partitions for HNSW.
                table.create_index(
                    "vector", config=HnswSq(distance_type="cosine", num_partitions=1)
                )

            def search(v):
                return table.search(v).distance_type("cosine").limit(TOP_K).to_list()

        elif db == "chroma-unpadded":
            # End-to-end through Chroma's own embedder, queries unpadded.
            import chromadb
            from chromadb.config import Settings

            col = chromadb.EphemeralClient(
                Settings(anonymized_telemetry=False)
            ).create_collection(
                "bench",
                embedding_function=unpadded_chroma_ef(),
                configuration={"hnsw": {"space": "cosine"}},
            )
            # Same MiniLM vectors as Chroma would compute.
            for i in range(0, len(docs), 250):
                col.add(
                    ids=[d["id"] for d in docs[i : i + 250]],
                    embeddings=vecs[i : i + 250],
                    documents=texts[i : i + 250],
                )

            def embed(q: str) -> str:  # embedding happens inside col.query
                return q

            def search(q):
                return col.query(query_texts=[q], n_results=TOP_K)["ids"][0]

        elif db == "chroma":
            import chromadb
            from chromadb.config import Settings

            col = chromadb.EphemeralClient(
                Settings(anonymized_telemetry=False)
            ).create_collection("bench", configuration={"hnsw": {"space": "cosine"}})
            for i in range(0, len(docs), 250):  # docs: 50-250 per add
                col.add(
                    ids=[d["id"] for d in docs[i : i + 250]],
                    embeddings=vecs[i : i + 250],
                    documents=texts[i : i + 250],
                )

            def search(v):
                return col.query(query_embeddings=[v], n_results=TOP_K)["ids"][0]

        elif db == "qdrant":
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, PointStruct, VectorParams

            client = QdrantClient(":memory:")
            client.create_collection(
                "bench",
                vectors_config=VectorParams(
                    size=len(vecs[0]), distance=Distance.COSINE
                ),
            )
            client.upload_points(
                "bench",
                [
                    PointStruct(id=i, vector=v, payload={"text": texts[i]})
                    for i, v in enumerate(vecs)
                ],
            )

            def search(v):
                return client.query_points("bench", query=v, limit=TOP_K).points

    print(
        f"  embedded {len(docs)} docs in {embed_s:.1f}s; built index in {t.elapsed_ms / 1000:.1f}s"
    )
    try:
        report(
            db,
            {
                k: v
                for k, v in measure(embed, search).items()
                if db != "chroma-unpadded" or k == "end-to-end"
            },
            f"{PKG[db]}={version(PKG[db])} fastembed={version('fastembed')}",
        )
    finally:
        if db.startswith("lancedb"):
            shutil.rmtree(path, ignore_errors=True)


async def run_moss(docs: list[dict]) -> None:
    from moss import DocumentInfo, MutationOptions, QueryOptions

    from moss_persist import client

    session = await client().session(
        f"bench-local-{uuid.uuid4().hex[:8]}"
    )  # unique: no cloud auto-load, never pushed
    with Timer() as t:
        await session.add_docs(
            [DocumentInfo(id=d["id"], text=d["text"]) for d in docs],
            MutationOptions(upsert=True),
        )
    print(f"  embedded + indexed {len(docs)} docs in {t.elapsed_ms / 1000:.1f}s")
    opts = QueryOptions(top_k=TOP_K, alpha=1.0)
    with Timer() as t:
        await session.query(QUERIES[0], opts)
    print(f"  cold query: {t.elapsed_ms:.3f} ms")
    for _ in range(WARMUP_ROUNDS):
        for q in QUERIES:
            await session.query(q, opts)
    e2e = []
    for _ in range(QUERY_ROUNDS):
        for q in QUERIES:
            with Timer() as t:
                r = await session.query(q, opts)
            assert len(r.docs) == TOP_K, r
            e2e.append(t.elapsed_ms)
    report("moss", {"end-to-end": e2e}, f"moss={version('moss')}")


def main() -> None:
    db = sys.argv[1]
    if db not in PKG:
        raise SystemExit(f"usage: bench_local.py {'|'.join(PKG)}")
    docs = json.loads((HERE / "bench_100k_docs.json").read_text())[:DOC_COUNT]
    if db == "moss":
        asyncio.run(run_moss(docs))
    else:
        run_competitor(db, docs)


if __name__ == "__main__":
    main()
