"""Query-embedding latency of tuned all-MiniLM-L6-v2 ONNX variants vs Moss native.

Run: .venv/bin/python bench_embed_tuning.py
"""

import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from fastembed import TextEmbedding
from moss_core import PyEmbeddingService
from onnxruntime.quantization import QuantType, quantize_dynamic
from tokenizers import Tokenizer

from bench_embed import measure
from bench_local import QUERIES, QUERY_ROUNDS, WARMUP_ROUNDS, report

CACHE = Path(__file__).parent / ".fastembed_cache"
MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def fastembed(**kw):
    model = TextEmbedding(MODEL, cache_dir=str(CACHE), **kw)
    return lambda q: next(iter(model.embed([q])))


def raw_ort(model_path: Path, tok: Tokenizer):
    """Tokenize + ORT run + mean pool; returns (embed fn, per-stage timings)."""
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    stages: dict[str, list[float]] = {"tokenize": [], "inference": []}

    def embed(q: str) -> np.ndarray:
        t0 = time.perf_counter()
        enc = tok.encode(q)
        feeds = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
            "token_type_ids": np.array([enc.type_ids], dtype=np.int64),
        }
        t1 = time.perf_counter()
        hidden = sess.run(None, feeds)[0][0]
        t2 = time.perf_counter()
        stages["tokenize"].append((t1 - t0) * 1000)
        stages["inference"].append((t2 - t1) * 1000)
        mask = feeds["attention_mask"][0][:, None]
        return (hidden * mask).sum(0) / mask.sum()

    return embed, stages


def main() -> None:
    moss = PyEmbeddingService("moss-minilm")
    moss.load_model()
    ref = {q: unit(moss.create_embedding(q)) for q in QUERIES}

    snap = next(
        (CACHE / "models--qdrant--all-MiniLM-L6-v2-onnx" / "snapshots").iterdir()
    )
    tok = Tokenizer.from_file(str(snap / "tokenizer.json"))
    int8 = CACHE / "minilm-int8.onnx"
    if not int8.exists():
        quantize_dynamic(snap / "model.onnx", int8, weight_type=QuantType.QInt8)

    variants = {
        "fastembed-default": fastembed(),
        **{f"fastembed-threads{n}": fastembed(threads=n) for n in (1, 2, 4, 8)},
        "fastembed-coreml": fastembed(providers=["CoreMLExecutionProvider"]),
    }
    raw_fp32, raw_fp32_stages = raw_ort(snap / "model.onnx", tok)
    raw_int8, raw_int8_stages = raw_ort(int8, tok)
    variants["raw-ort-fp32"] = raw_fp32
    variants["raw-ort-int8 (NOT same precision as Moss)"] = raw_int8
    variants["moss-native"] = lambda q: moss.create_embedding(q)

    for name, embed in variants.items():
        cos = [float(unit(embed(q)) @ ref[q]) for q in QUERIES]
        for s in (raw_fp32_stages, raw_int8_stages):
            for v in s.values():
                v.clear()  # stage timings only from the measured rounds below
        lat = measure(embed)
        series = {"embed": lat}
        if name.startswith("raw-ort"):
            stages = raw_fp32_stages if "fp32" in name else raw_int8_stages
            n = WARMUP_ROUNDS * len(QUERIES)
            series |= {k: v[n:] for k, v in stages.items()}  # drop warmup samples
        assert all(len(v) == QUERY_ROUNDS * len(QUERIES) for v in series.values())
        slug = name.split(" ")[0]
        report(
            f"tune-{slug}",
            series,
            f"cosine vs moss min={min(cos):.6f} mean={np.mean(cos):.6f}",
        )


if __name__ == "__main__":
    main()
