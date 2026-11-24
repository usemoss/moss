"""Compare Moss and competitor results on the synthetic sentence templates."""

from collections import Counter
import hashlib
import json
import re
from statistics import mean


ENGINES = ("pinecone", "qdrant", "chroma")
TOP_K = 5
SCHEMA_VERSION = 1
VARIANT_SUFFIX = re.compile(r" \(variant [0-9]+, context [0-9]+\)\Z")
MODEL_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*")


def sentence_template(text):
    """Remove the generated suffix while preserving the original sentence."""
    suffix = VARIANT_SUFFIX.search(text)
    if suffix is None or not text[:suffix.start()].strip():
        raise ValueError("Expected a sentence with a benchmark variant/context suffix")
    return text[:suffix.start()]


def _validate_rankings(rankings, queries, source):
    if not isinstance(rankings, dict) or set(rankings) != set(queries):
        raise ValueError(f"{source} rankings must cover exactly the benchmark queries")
    for ids in rankings.values():
        if (
            not isinstance(ids, list)
            or len(ids) != TOP_K
            or any(not isinstance(doc_id, str) or not doc_id.strip() for doc_id in ids)
            or len(set(ids)) != TOP_K
        ):
            raise ValueError(f"{source} rankings must have {TOP_K} unique document IDs per query")


def _validate_reference(reference, dataset_sha256, queries):
    if (
        not isinstance(reference, dict)
        or type(reference.get("schema_version")) is not int
        or reference["schema_version"] != SCHEMA_VERSION
    ):
        raise ValueError("Unsupported competitor reference schema")
    if (
        not isinstance(dataset_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", dataset_sha256)
        or reference.get("dataset_sha256") != dataset_sha256
    ):
        raise ValueError("Competitor reference corpus SHA-256 does not match the benchmark")
    if reference.get("top_k") != TOP_K or reference.get("queries") != queries:
        raise ValueError("Competitor reference query workload does not match the benchmark")

    embedding_models = reference.get("embedding_models")
    if not isinstance(embedding_models, dict) or set(embedding_models) != set(ENGINES):
        raise ValueError("Competitor reference needs Pinecone, Qdrant, and Chroma embedding model labels")
    if any(not isinstance(label, str) or not MODEL_LABEL.fullmatch(label) for label in embedding_models.values()):
        raise ValueError("Competitor embedding model labels must be public model identifiers")

    rankings = reference.get("rankings")
    if not isinstance(rankings, dict) or set(rankings) != set(ENGINES):
        raise ValueError("Competitor reference needs Pinecone, Qdrant, and Chroma rankings")
    for engine in ENGINES:
        _validate_rankings(rankings[engine], queries, engine)


def make_reference(dataset_sha256, queries, rankings, embedding_models):
    """Build a JSON-ready reference from the three engines' original corpus IDs."""
    reference = {
        "schema_version": SCHEMA_VERSION,
        "dataset_sha256": dataset_sha256,
        "queries": list(queries),
        "top_k": TOP_K,
        "embedding_models": embedding_models,
        "rankings": rankings,
    }
    _validate_reference(reference, dataset_sha256, reference["queries"])
    return reference


def load_reference(path, dataset_sha256, queries):
    """Validate a saved reference against the current workload and hash its exact bytes."""
    raw = path.read_bytes()
    reference = json.loads(raw)
    _validate_reference(reference, dataset_sha256, list(queries))
    reference["reference_sha256"] = hashlib.sha256(raw).hexdigest()
    return reference


def _templates_for(ids, templates):
    try:
        return {templates[doc_id] for doc_id in ids}
    except KeyError:
        raise ValueError("Agreement rankings contain document IDs absent from the benchmark corpus") from None


def score_agreement(reference, moss_rankings, templates):
    """Measure coverage of templates returned by at least two competitors."""
    queries = reference["queries"]
    _validate_rankings(moss_rankings, queries, "Moss")
    per_query = {}
    scored = []
    for query in queries:
        votes = Counter()
        for engine in ENGINES:
            votes.update(_templates_for(reference["rankings"][engine][query], templates))
        consensus = {template for template, votes_cast in votes.items() if votes_cast >= 2}
        moss_templates = _templates_for(moss_rankings[query], templates)
        matched = len(consensus & moss_templates)
        agreement = matched / len(consensus) if consensus else None
        per_query[query] = {
            "agreement": agreement,
            "consensus_template_count": len(consensus),
            "matched_template_count": matched,
        }
        if agreement is not None:
            scored.append(agreement)

    return {
        "metric": "competitor_template_agreement_at_5",
        "status": "measured" if scored else "no_consensus",
        "mean_agreement": mean(scored) if scored else None,
        "scored_queries": len(scored),
        "unscored_queries": len(queries) - len(scored),
        "per_query": per_query,
        "reference": {
            "sha256": reference.get("reference_sha256"),
            "dataset_sha256": reference["dataset_sha256"],
            "embedding_models": reference["embedding_models"],
            "engines": list(ENGINES),
        },
    }
