"""Offline checks for the collector's scalar metric configuration."""

import importlib
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
capture = importlib.import_module("capture_competitor_rankings")


class CaptureConfigurationTests(unittest.TestCase):
    def test_accepts_explicit_cosine_and_documented_model_defaults(self):
        for model, metric in (
            ("llama-text-embed-v2", None),
            ("multilingual-e5-large", None),
            ("another-model", "cosine"),
        ):
            with self.subTest(model=model, metric=metric):
                capture.validate_pinecone_metric(model, metric)

    def test_rejects_non_cosine_metrics_and_unknown_defaults(self):
        for model, metric in (
            ("llama-text-embed-v2", "dotproduct"),
            ("multilingual-e5-large", "euclidean"),
            ("another-model", None),
        ):
            with self.subTest(model=model, metric=metric), self.assertRaises(capture.CaptureError):
                capture.validate_pinecone_metric(model, metric)
