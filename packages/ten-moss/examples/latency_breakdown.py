"""Latency breakdown for a Moss session managed by ``ten-moss``.

Shows exactly where time goes when you ground a turn with Moss:

* the **one-time** cost of opening the session (create-or-resume + load the
  in-process index), paid once at startup, and
* the **per-turn** retrieval cost — both the engine-measured time from the
  ``SearchResult`` (``MossSessionManager.last_time_taken_ms``) and the wall-clock
  time around ``query_context`` (which also includes query embedding + Python).

Run ``examples/create_index.py`` first to populate ``MOSS_INDEX_NAME``.

Usage:
    export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=...
    python examples/latency_breakdown.py            # default question set
    python examples/latency_breakdown.py -n 200     # more samples
"""

import argparse
import asyncio
import os
import statistics
import time

from ten_moss import MossSessionManager

try:  # python-dotenv is optional; real env vars work too.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*args, **kwargs):
        """No-op fallback when python-dotenv is not installed."""
        return False


QUESTIONS = [
    "How long do refunds take?",
    "Can I cancel my order after I place it?",
    "Which payment methods can I use?",
    "How fast is express shipping?",
    "How do I track my order?",
]


def _pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile (values need not be pre-sorted)."""
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))]


def _fmt(values: list[float]) -> str:
    return (
        f"p50={_pct(values, 0.50):6.1f} ms   "
        f"p95={_pct(values, 0.95):6.1f} ms   "
        f"mean={statistics.mean(values):6.1f} ms"
    )


async def main(samples: int) -> None:
    load_dotenv()
    session = MossSessionManager(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
        index_name=os.environ.get("MOSS_INDEX_NAME", "ten-moss-demo"),
        top_k=5,
        alpha=0.8,
    )

    # --- one-time: open the session (create-or-resume + load the index) ---
    t0 = time.perf_counter()
    await session.open()
    open_ms = (time.perf_counter() - t0) * 1000.0

    # warm-up (first query loads the embedding model; not measured)
    for q in QUESTIONS:
        await session.query_context(q)

    # --- per-turn: measure query_context over `samples` calls ---
    engine_ms: list[float] = []  # SearchResult.time_taken_ms (engine)
    wall_ms: list[float] = []  # wall-clock around query_context (engine + embed + python)
    i = 0
    while len(wall_ms) < samples:
        q = QUESTIONS[i % len(QUESTIONS)]
        i += 1
        t = time.perf_counter()
        await session.query_context(q)
        wall_ms.append((time.perf_counter() - t) * 1000.0)
        if session.last_time_taken_ms is not None:
            engine_ms.append(float(session.last_time_taken_ms))

    print("\nMoss session · latency breakdown")
    print(f"  index: {os.environ.get('MOSS_INDEX_NAME', 'ten-moss-demo')}   docs: {session.doc_count}\n")

    print("One-time (paid once at startup)")
    print(f"  session open (create-or-resume + load index): {open_ms:8.1f} ms\n")

    print(f"Per-turn retrieval · query_context  (n={len(wall_ms)})")
    if engine_ms:
        emean = statistics.mean(engine_ms)
        if emean < 1:
            # int-ms field rounds sub-millisecond search to 0 — say so plainly.
            print("  hybrid search engine (SearchResult.time_taken_ms):  <1 ms  (sub-millisecond, in-process)")
        else:
            print(f"  hybrid search engine (SearchResult.time_taken_ms):  {_fmt(engine_ms)}")
    print(f"  end-to-end query_context (search + query embed):    {_fmt(wall_ms)}\n")

    print("  The hybrid search itself is sub-millisecond; the end-to-end cost is mostly")
    print("  query embedding. Either way it's in-process — no network hop. For contrast, a")
    print("  cloud retrieval round-trip is typically 200-1500 ms, paid on EVERY turn.")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Moss session latency breakdown via ten-moss.")
    parser.add_argument("-n", "--samples", type=int, default=100, help="number of query_context samples")
    args = parser.parse_args()
    asyncio.run(main(args.samples))


if __name__ == "__main__":
    _cli()
