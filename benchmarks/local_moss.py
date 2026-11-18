"""Fresh local-session benchmark over the checked-in full corpus.

Only public SessionIndex operations are used. No cloud index is created,
loaded, or pushed, and document snapshots are neither saved nor restored.
SDK authentication, model download, and usage reporting still apply.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import bench_moss
from bench_moss import Measurement, measure_queries
from corpus import get_queries, load_fixed_documents

MODEL_ID = "moss-minilm"
LOCAL_INDEX_NAME = "benchmark-local-100k"
BATCH_SIZE = 5_000


@dataclass
class LocalRun:
    """Measured queries and the data/setup facts that make a run interpretable."""

    measurement: Measurement
    configuration: dict
    setup: dict


async def run_local_async(project_id, project_key, *, corpus_path=None) -> LocalRun:
    """Build the entire corpus in a fresh session, then measure the legacy workload."""
    if not all(isinstance(v, str) and v.strip() for v in (project_id, project_key)):
        raise ValueError("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be supplied")
    documents, dataset_sha = load_fixed_documents(
        corpus_path, expected_count=bench_moss.DOC_COUNT
    )
    queries = get_queries()
    expected_ids = {row["id"] for row in documents}

    # Defer SDK imports so the workload and corpus checks remain testable offline.
    from moss import MossClient, QueryOptions

    configuration = {
        "mode": "local-session",
        "setup_mode": "fresh-build",
        "dataset_sha256": dataset_sha,
        "query_sha256": hashlib.sha256(
            json.dumps(queries, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest(),
        "model_id": MODEL_ID,
        "model_artifact_id": None,
        "model_artifact_note": (
            "The public SessionIndex API exposes the model alias, not its exact "
            "artifact identity. Every run builds a fresh document index."
        ),
        "doc_count": len(documents),
        "query_count": len(queries),
        "top_k": bench_moss.TOP_K,
        "alpha": 1,
        "warmup_rounds": bench_moss.WARMUP_ROUNDS,
        "query_rounds": bench_moss.QUERY_ROUNDS,
    }
    setup = {}
    opening = time.perf_counter()
    sdk_cache = Path(__file__).resolve().parent.parent / ".moss-cache"
    async with MossClient(project_id, project_key, cache_path=str(sdk_cache)) as client:
        async with await client.session(
            LOCAL_INDEX_NAME, model_id=MODEL_ID, auto_load_on_init=False
        ) as session:
            setup["session_open_seconds"] = time.perf_counter() - opening
            if session.doc_count != 0:
                raise ValueError("Expected a fresh, empty benchmark session")
            build_start = time.perf_counter()
            for start in range(0, len(documents), BATCH_SIZE):
                batch = documents[start : start + BATCH_SIZE]
                added, updated = await session.add_docs(batch)
                if added != len(batch) or updated != 0:
                    raise ValueError("Local index build did not add the expected documents")
                if session.doc_count != start + len(batch):
                    raise ValueError("Local index document count disagrees with the corpus")
                print(f"  Indexed {session.doc_count:,}/{len(documents):,} locally", flush=True)
            setup["build_seconds"] = time.perf_counter() - build_start
            if session.doc_count != len(documents) or session.model_id != MODEL_ID:
                raise ValueError("Local index size or model does not match the benchmark")
            configuration["actual_doc_count"] = session.doc_count
            options = QueryOptions(top_k=bench_moss.TOP_K, alpha=1)

            async def query(text):
                """Bind local-session query options without adding timed validation."""
                return await session.query(text, options)

            measurement = await measure_queries(
                query,
                queries,
                name=f"Moss LOCAL SESSION (top_k={bench_moss.TOP_K}, {len(documents)} docs)",
                expected_ids=expected_ids,
            )
    return LocalRun(measurement, configuration, setup)
