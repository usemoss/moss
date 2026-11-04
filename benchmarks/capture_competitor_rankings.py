"""Capture a one-off reference from the three systems' text search paths.

Pinecone embeds text in an existing integrated index. Chroma and Qdrant
embed locally and run in memory. See the benchmark README for setup.
"""

import argparse
from contextlib import closing
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

from bench_moss import TOP_K
from competitor_agreement import make_reference
from corpus import FIXED_CORPUS_PATH, get_queries, load_fixed_documents
from run_ci import write_record


QDRANT_MODEL = "BAAI/bge-small-en-v1.5"
LOCAL_BATCH_SIZE = 256
PINECONE_BATCH_SIZE = 96


class CaptureError(Exception):
    """A capture failure with a message safe to show on the console."""


def local_rankings(namespace, documents, queries):
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction, ONNXMiniLM_L6_V2
    from qdrant_client import QdrantClient, models

    chroma_client = chromadb.EphemeralClient(settings=Settings(anonymized_telemetry=False))
    chroma = chroma_client.create_collection(
        name=namespace,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=DefaultEmbeddingFunction(),
    )
    with closing(QdrantClient(":memory:")) as qdrant:
        try:
            dimension = qdrant.get_embedding_size(QDRANT_MODEL)
        except ImportError:
            raise CaptureError("Install qdrant-client with the fastembed extra") from None
        qdrant.create_collection(
            namespace,
            vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
        )
        print("Indexing the fixed corpus in local Chroma and Qdrant", flush=True)
        for start in range(0, len(documents), LOCAL_BATCH_SIZE):
            batch = documents[start : start + LOCAL_BATCH_SIZE]
            chroma.add(ids=[row["id"] for row in batch], documents=[row["text"] for row in batch])
            qdrant.upsert(
                collection_name=namespace,
                points=[
                    models.PointStruct(
                        id=i, vector=models.Document(text=row["text"], model=QDRANT_MODEL)
                    )
                    for i, row in enumerate(batch, start)
                ],
                wait=True,
            )
            if (start // LOCAL_BATCH_SIZE + 1) % 20 == 0:
                print(f"Indexed {start + len(batch):,}/{len(documents):,} documents locally", flush=True)

        if chroma.count() != len(documents) or qdrant.count(namespace, exact=True).count != len(documents):
            raise CaptureError("Chroma or Qdrant index size does not match the fixed corpus")
        chroma_ids = chroma.query(query_texts=queries, n_results=TOP_K, include=[])["ids"]
        rankings = {"chroma": dict(zip(queries, chroma_ids, strict=True)), "qdrant": {}}
        for query in queries:
            points = qdrant.query_points(
                collection_name=namespace,
                query=models.Document(text=query, model=QDRANT_MODEL),
                limit=TOP_K,
                with_payload=False,
            ).points
            if any(type(point.id) is not int or not 0 <= point.id < len(documents) for point in points):
                raise CaptureError("Qdrant returned an unknown point ID")
            rankings["qdrant"][query] = [documents[point.id]["id"] for point in points]
    return rankings, ONNXMiniLM_L6_V2.MODEL_NAME


def pinecone_text_field(description):
    from pinecone.models.indexes.schema import SemanticTextField

    fields = [
        (name, field)
        for name, field in description.schema.fields.items()
        if isinstance(field, SemanticTextField)
    ]
    if not description.status.ready or not description.host or len(fields) != 1:
        raise CaptureError("Pinecone needs a ready integrated text embedding index with cosine distance")
    field_name, field = fields[0]
    if field.metric != "cosine" or field_name in {"_id", "id"}:
        raise CaptureError("Pinecone needs cosine distance and a text field distinct from the record ID")
    return field_name, field.model


def wait_for_pinecone(index, namespace, count):
    deadline = time.monotonic() + 600
    while (remaining := deadline - time.monotonic()) > 0:
        summary = index.describe_index_stats(timeout=min(30, remaining)).namespaces.get(namespace)
        indexed = summary.vector_count if summary else 0
        if indexed == count:
            return
        if indexed > count:
            raise CaptureError("Pinecone namespace contains more vectors than the fixed corpus")
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise CaptureError("Timed out waiting for the complete Pinecone namespace to become searchable")


def pinecone_rankings(index, namespace, field_name, documents, queries):
    from pinecone import NotFoundError

    print(f"Indexing the fixed corpus in Pinecone namespace {namespace}", flush=True)
    try:
        for start in range(0, len(documents), PINECONE_BATCH_SIZE):
            batch = documents[start : start + PINECONE_BATCH_SIZE]
            index.upsert_records(
                records=[{"_id": row["id"], field_name: row["text"]} for row in batch],
                namespace=namespace,
            )
            if (start // PINECONE_BATCH_SIZE + 1) % 50 == 0:
                print(f"Uploaded {start + len(batch):,}/{len(documents):,} Pinecone records", flush=True)
        wait_for_pinecone(index, namespace, len(documents))
        rankings = {}
        for query in queries:
            result = index.search(namespace=namespace, top_k=TOP_K, inputs={"text": query})
            rankings[query] = [hit.id for hit in result.result.hits]
        return rankings
    finally:
        try:
            index.delete_namespace(name=namespace)
        except NotFoundError:
            pass
        except Exception:
            raise CaptureError(f"Pinecone cleanup failed for temporary namespace {namespace}") from None


def capture():
    key = os.environ.get("PINECONE_API_KEY", "").strip()
    index_name = os.environ.get("PINECONE_INDEX_NAME", "").strip()
    if not key or not index_name:
        raise CaptureError("Set PINECONE_API_KEY and PINECONE_INDEX_NAME for an existing dedicated index")

    from pinecone import Pinecone

    documents, dataset_sha256 = load_fixed_documents()
    queries = get_queries()
    known_ids = {row["id"] for row in documents}
    namespace = f"benchmark-{uuid4().hex}"
    with Pinecone(api_key=key) as pinecone:
        description = pinecone.indexes.describe(index_name)
        field_name, pinecone_model = pinecone_text_field(description)
        rankings, chroma_model = local_rankings(namespace, documents, queries)
        with pinecone.index(host=description.host) as index:
            rankings["pinecone"] = pinecone_rankings(index, namespace, field_name, documents, queries)

    for backend, by_query in rankings.items():
        if any(not known_ids.issuperset(result_ids) for result_ids in by_query.values()):
            raise CaptureError(f"{backend} returned an unknown document ID")
    models = {"pinecone": pinecone_model, "qdrant": QDRANT_MODEL, "chroma": chroma_model}
    return make_reference(dataset_sha256, queries, rankings, models)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--env-file", type=Path, help="Explicit credentials file")
    args = parser.parse_args(argv)
    if args.output.resolve() == FIXED_CORPUS_PATH.resolve():
        parser.error("--output must be different from the fixed corpus path")
    if args.env_file:
        if not args.env_file.is_file() or args.env_file.resolve() == args.output.resolve():
            parser.error("--env-file must be an existing file distinct from --output")
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=args.env_file)
    try:
        write_record(args.output, capture(), ())
    except CaptureError as error:
        print(error, file=sys.stderr)
        return 1
    except Exception as error:
        # Vendor errors may include account details or a private endpoint URL.
        print(f"Competitor reference capture failed ({type(error).__name__})", file=sys.stderr)
        return 1
    print(f"Wrote competitor reference to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
