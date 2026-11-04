"""Offline checks for the competitor reference and template agreement metric."""

import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
agreement = importlib.import_module("competitor_agreement")

DATASET_SHA = "a" * 64
EMBEDDING_MODELS = {
    "pinecone": "pinecone-test-model",
    "qdrant": "example/qdrant-test-model",
    "chroma": "chroma-test-model",
}


def doc_ids(start, count=5):
    return [f"doc_{index}" for index in range(start, start + count)]


class CompetitorAgreementTests(unittest.TestCase):
    def setUp(self):
        self.queries = ["partial", "complete", "unscored"]
        self.rankings = {
            engine: {"partial": doc_ids(start), "complete": doc_ids(start), "unscored": doc_ids(start + 15)}
            for engine, start in (("pinecone", 0), ("qdrant", 5), ("chroma", 10))
        }
        # Give the complete query one agreed template so averaging per query
        # differs from pooling template matches across queries.
        self.rankings["qdrant"]["complete"][1] = "doc_31"
        self.templates = {doc_id: doc_id for doc_id in doc_ids(0, 32)}
        self.templates.update({
            "doc_0": "Pinecone and Qdrant", "doc_1": "Pinecone and Qdrant", "doc_5": "Pinecone and Qdrant",
            "doc_2": "Pinecone only", "doc_3": "Pinecone only",
            "doc_6": "Qdrant and Chroma", "doc_10": "Qdrant and Chroma",
        })
        self.reference = agreement.make_reference(DATASET_SHA, self.queries, self.rankings, EMBEDDING_MODELS)
        self.moss = {
            "partial": ["doc_0", "doc_1", "doc_2", "doc_3", "doc_30"],
            "complete": ["doc_0", "doc_1", "doc_6", "doc_10", "doc_30"],
            "unscored": doc_ids(15),
        }

    def test_counts_distinct_template_votes_and_averages_only_scored_queries(self):
        report = agreement.score_agreement(self.reference, self.moss, self.templates)
        self.assertEqual(report["status"], "measured")
        self.assertEqual((report["scored_queries"], report["unscored_queries"]), (2, 1))
        self.assertEqual(report["mean_agreement"], 0.75)
        self.assertEqual(report["reference"]["embedding_models"], EMBEDDING_MODELS)
        self.assertEqual(report["per_query"], {
            "partial": {"agreement": 0.5, "consensus_template_count": 2, "matched_template_count": 1},
            "complete": {"agreement": 1.0, "consensus_template_count": 1, "matched_template_count": 1},
            "unscored": {"agreement": None, "consensus_template_count": 0, "matched_template_count": 0},
        })

    def test_no_consensus_has_no_numeric_mean(self):
        query = "unscored"
        rankings = {engine: {query: by_query[query]} for engine, by_query in self.rankings.items()}
        reference = agreement.make_reference(DATASET_SHA, [query], rankings, EMBEDDING_MODELS)
        report = agreement.score_agreement(reference, {query: self.moss[query]}, self.templates)
        self.assertEqual(report["status"], "no_consensus")
        self.assertIsNone(report["mean_agreement"])

    def test_loads_reference_hash_and_rejects_incompatible_or_malformed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.json"
            raw = json.dumps(self.reference).encode()
            path.write_bytes(raw)
            loaded = agreement.load_reference(path, DATASET_SHA, self.queries)
            self.assertEqual(loaded["reference_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(loaded["embedding_models"], EMBEDDING_MODELS)
            for dataset, queries, message in (
                ("b" * 64, self.queries, "corpus SHA-256"),
                (DATASET_SHA, self.queries[:-1], "query workload"),
            ):
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    agreement.load_reference(path, dataset, queries)

            self.reference["rankings"]["pinecone"]["partial"] = ["doc_0"] * 5
            path.write_text(json.dumps(self.reference), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique document IDs"):
                agreement.load_reference(path, DATASET_SHA, self.queries)

    def test_requires_one_valid_model_label_per_engine(self):
        for models in (
            {engine: model for engine, model in EMBEDDING_MODELS.items() if engine != "pinecone"},
            {**EMBEDDING_MODELS, "other": "unexpected-model"},
            {**EMBEDDING_MODELS, "chroma": " "},
            {**EMBEDDING_MODELS, "chroma": "https://example.invalid/model"},
            {**EMBEDDING_MODELS, "chroma": "api_key=fake-secret"},
        ):
            with self.subTest(models=models), self.assertRaises(ValueError):
                agreement.make_reference(DATASET_SHA, self.queries, self.rankings, models)

    def test_unknown_competitor_or_moss_ids_fail_scoring(self):
        for missing_id in ("doc_5", "doc_30"):
            with self.subTest(missing_id=missing_id):
                templates = self.templates.copy()
                del templates[missing_id]
                with self.assertRaisesRegex(ValueError, "absent from the benchmark corpus"):
                    agreement.score_agreement(self.reference, self.moss, templates)

    def test_sentence_template_removes_only_the_generated_suffix(self):
        sentence = "A sentence containing (variant 9, context 8) in its text"
        self.assertEqual(agreement.sentence_template(f"{sentence} (variant 1, context 2)"), sentence)
        with self.assertRaises(ValueError):
            agreement.sentence_template(sentence)


if __name__ == "__main__":
    unittest.main()
