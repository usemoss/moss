"""Does batched ingest need padding, and how much? MiniLM-L6-v2 on one ONNX Runtime session.

Strategies: unbatched/unpadded, fixed pad to 256 (Chroma default), dynamic pad to the batch's
longest doc, and dynamic pad after sorting docs by length. Vectors are checked against unbatched.
Run: .venv/bin/python batch_padding.py
"""

import glob
import json
import time

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from bench_local import HERE, RESULTS
from doc_chunk_eval import OUT

SNAP = glob.glob(
    str(HERE / ".fastembed_cache/models--qdrant--all-MiniLM-L6-v2-onnx/snapshots/*/")
)[0]
SESS = ort.InferenceSession(SNAP + "/model.onnx", providers=["CPUExecutionProvider"])
TOK = Tokenizer.from_file(SNAP + "/tokenizer.json")
TOK.no_padding()
TOK.enable_truncation(max_length=256)
BATCH = 32


def run(encs: list, pad_to: int | None) -> np.ndarray:
    """Embed one batch; pad_to=None pads to the batch's longest encoding."""
    n = pad_to or max(len(e.ids) for e in encs)
    ids = np.zeros((len(encs), n), dtype=np.int64)
    mask = np.zeros_like(ids)
    for i, e in enumerate(encs):
        ids[i, : len(e.ids)] = e.ids
        mask[i, : len(e.ids)] = 1
    hidden = SESS.run(
        None,
        {
            "input_ids": ids,
            "attention_mask": mask,
            "token_type_ids": np.zeros_like(ids),
        },
    )[0]
    v = (hidden * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def strategy(encs: list, name: str) -> np.ndarray:
    order = (
        sorted(range(len(encs)), key=lambda i: len(encs[i].ids))
        if name == "dynamic, length-sorted"
        else list(range(len(encs)))
    )
    out = np.zeros((len(encs), 384), dtype=np.float32)
    if name == "unbatched, unpadded":
        for i, e in enumerate(encs):
            out[i] = run([e], None)[0]
        return out
    for s in range(0, len(order), BATCH):
        idx = order[s : s + BATCH]
        out[idx] = run(
            [encs[i] for i in idx], 256 if name == "batch 32, fixed pad 256" else None
        )
    return out


def main() -> None:
    lines = []
    for corpus in ("paper", "small"):
        docs = json.loads((OUT / f"builtin-{corpus}-docs.json").read_text())
        encs = TOK.encode_batch([d["text"] for d in docs])
        real = sum(len(e.ids) for e in encs)
        run(encs[:BATCH], None)  # warm up
        base = None
        for name in (
            "unbatched, unpadded",
            "batch 32, fixed pad 256",
            "batch 32, dynamic pad",
            "dynamic, length-sorted",
        ):
            t0 = time.perf_counter()
            v = strategy(encs, name)
            s = time.perf_counter() - t0
            base = v if base is None else base
            cos = float((v * base).sum(1).min())
            line = f"{corpus:5} {name:26} {s:6.2f}s  {len(docs) / s:6.0f} docs/s  {real / s:7.0f} real tok/s  min cosine vs unbatched {cos:.6f}"
            print(line, flush=True)
            lines.append(line)
    (RESULTS / "batch_padding.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
