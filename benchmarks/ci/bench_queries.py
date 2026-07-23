"""Shared configuration for the CI benchmark suite.

Both the benchmark tests (``test_bench_ci_moss.py``) and the ground-truth
generator (``generate_ground_truth.py``) import from this module so the
query set can never drift between generation and evaluation.
"""

INDEX_NAME_DEFAULT = "benchmark-ci"
MODEL_ID = "moss-minilm"
DOC_COUNT = 1_000

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
