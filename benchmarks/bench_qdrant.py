"""Benchmark: Qdrant — external embedding + local in-memory vector search.

This measures end-to-end latency: embed the query via an external API,
then search a local in-memory Qdrant index.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from corpus import get_documents, get_queries
from embedding import EmbeddingClient
from stats import Timer, BenchmarkResult

DOC_COUNT = 100_000
TOP_K = 5
WARMUP_ROUNDS = 3
QUERY_ROUNDS = 50
COLLECTION = "benchmark"


def run():
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    embed = EmbeddingClient()
    docs = get_documents(DOC_COUNT)
    queries = get_queries()

    print(f"  docs in index  : {DOC_COUNT}")
    print(f"  warmup rounds  : {WARMUP_ROUNDS}")
    print(f"  query rounds   : {QUERY_ROUNDS}")
    print(f"  queries/round  : {len(queries)}")
    print(f"  embedding      : {embed.provider} (dim={embed.dimension})")

    # --- Setup Qdrant (in-memory) ---
    client = QdrantClient(":memory:")
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(
            size=embed.dimension, distance=Distance.COSINE
        ),
    )

    # --- Embed and upsert documents ---
    print("  Embedding and upserting documents...")
    BATCH = 100
    for i in range(0, len(docs), BATCH):
        batch = docs[i : i + BATCH]
        texts = [d["text"] for d in batch]
        embeddings = embed.embed_batch(texts)
        points = [
            PointStruct(
                id=i + j,
                vector=emb,
                payload={"text": d["text"], **(d.get("metadata") or {})},
            )
            for j, (d, emb) in enumerate(zip(batch, embeddings))
        ]
        client.upsert(collection_name=COLLECTION, points=points)

    print(f"  Loaded {client.count(COLLECTION).count} docs")

    def qdrant_search(query_vector):
        """Compatibility wrapper for qdrant-client API changes."""
        if hasattr(client, "search"):
            return client.search(
                collection_name=COLLECTION,
                query_vector=query_vector,
                limit=TOP_K,
            )
        return client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            limit=TOP_K,
        )

    # --- Cold query ---
    with Timer() as t:
        emb = embed.embed(queries[0])
        qdrant_search(emb)
    print(f"\n  Cold query: {t.elapsed_ms:.3f} ms")

    # --- Warmup ---
    print(f"\n  Warming up ({WARMUP_ROUNDS} rounds)...")
    for _ in range(WARMUP_ROUNDS):
        for q in queries:
            emb = embed.embed(q)
            qdrant_search(emb)

    # --- Measure ---
    print(f"  Measuring ({QUERY_ROUNDS} rounds x {len(queries)} queries)...\n")
    latencies = []
    for _ in range(QUERY_ROUNDS):
        for q in queries:
            with Timer() as t:
                emb = embed.embed(q)
                qdrant_search(emb)
            latencies.append(t.elapsed_ms)

    result = BenchmarkResult(
        f"Qdrant local (external embed + in-memory search, top_k={TOP_K}, {DOC_COUNT} docs)",
        latencies,
    )
    print(result.summary())
    return result


if __name__ == "__main__":
    run()
