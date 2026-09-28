"""Query-embedding latency: fastembed ONNX all-MiniLM-L6-v2 vs Moss native moss-minilm.

Uses moss_core.PyEmbeddingService, an internal (undocumented) Moss core API.
Run: .venv/bin/python bench_embed.py
"""

from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from moss_core import PyEmbeddingService

from bench_local import QUERIES, QUERY_ROUNDS, WARMUP_ROUNDS, report
from stats import Timer


def measure(embed) -> list[float]:
    for _ in range(WARMUP_ROUNDS):
        for q in QUERIES:
            embed(q)
    latencies = []
    for _ in range(QUERY_ROUNDS):
        for q in QUERIES:
            with Timer() as t:
                embed(q)
            latencies.append(t.elapsed_ms)
    return latencies


def main() -> None:
    fe = TextEmbedding(
        "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir=str(Path(__file__).parent / ".fastembed_cache"),
    )
    moss = PyEmbeddingService("moss-minilm")
    moss.load_model()

    def fe_embed(q: str) -> np.ndarray:
        return next(iter(fe.embed([q])))

    def moss_embed(q: str) -> np.ndarray:
        return np.asarray(moss.create_embedding(q), dtype=np.float32)

    cos = [float(fe_embed(q) @ moss_embed(q)) for q in QUERIES]  # both L2-normalized
    print(
        f"  dims fastembed={fe_embed(QUERIES[0]).shape[0]} moss={moss_embed(QUERIES[0]).shape[0]}"
    )
    print(
        f"  cosine(fastembed, moss) per query: min={min(cos):.6f} mean={np.mean(cos):.6f} max={max(cos):.6f}"
    )
    report("embed-fastembed", {"embed": measure(fe_embed)})
    report("embed-moss-native", {"embed": measure(moss_embed)})


if __name__ == "__main__":
    main()
