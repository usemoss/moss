"""Gold-phrase bench. python bench/run.py --echo-grounding

No LLM key. Tool arm always searches (no model). Without MOSS_* the
FAQ file is used and moss_retrieval_ms is n/a.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*_args, **_kwargs):
        return False

HERE = Path(__file__).resolve().parent
QUERIES_PATH = HERE / "queries.jsonl"
KNOWLEDGE_PATH = HERE.parent / "data" / "knowledge.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_queries(path: Path = QUERIES_PATH) -> list[dict]:
    return load_jsonl(path)


def contains_gold(text: str, gold: list[str]) -> bool:
    haystack = text or ""
    return any(phrase in haystack for phrase in gold)


def lookup_faq(query: str, queries: list[dict], docs: list[dict]) -> str:
    by_id = {str(doc.get("id")): doc for doc in docs}
    for row in queries:
        if row.get("query") == query:
            doc = by_id.get(str(row.get("id")))
            if doc:
                return f"Relevant knowledge from Moss:\n\n[1] {doc.get('text', '')}"
    return ""


async def query_moss(session, query: str) -> tuple[str, float | None, float | None]:
    t0 = time.perf_counter()
    try:
        context = await session.query_context(query)
    except Exception:
        return "", None, (time.perf_counter() - t0) * 1000.0
    wall_ms = (time.perf_counter() - t0) * 1000.0
    sdk_ms = getattr(session, "last_time_taken_ms", None)
    return context or "", float(sdk_ms) if sdk_ms is not None else None, wall_ms


async def open_moss():
    load_dotenv(HERE.parent / ".env")
    load_dotenv(HERE.parent / ".env.local", override=True)
    project_id = os.environ.get("MOSS_PROJECT_ID", "").strip()
    project_key = os.environ.get("MOSS_PROJECT_KEY", "").strip()
    index_name = os.environ.get("MOSS_INDEX_NAME", "").strip()
    if not (project_id and project_key and index_name):
        return None
    try:
        from ten_moss import MossSessionManager
    except ImportError:
        return None
    session = MossSessionManager(
        project_id=project_id,
        project_key=project_key,
        index_name=index_name,
        model_id=os.environ.get("MOSS_MODEL_ID", "moss-minilm"),
        top_k=3,
        alpha=0.8,
    )
    try:
        await session.open()
    except Exception as exc:
        print(f"warning: Moss session failed to open ({exc}); using local FAQ lookup", file=sys.stderr)
        return None
    return session


def format_ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] * (1.0 - (k - lo)) + ordered[hi] * (k - lo)


def render_table(rows: list[dict]) -> str:
    lines = [
        "| query | arm | moss_retrieval_ms | moss_wall_ms | hit | faithful | tool_called |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        tool = "yes" if row["tool_called"] else "no" if row["arm"] == "tool" else "-"
        lines.append(
            f"| {row['query']} | {row['arm']} | {format_ms(row['moss_retrieval_ms'])} | "
            f"{format_ms(row['moss_wall_ms'])} | "
            f"{'yes' if row['hit'] else 'no'} | "
            f"{'yes' if row['faithful'] else 'no'} | {tool} |"
        )
    return "\n".join(lines)


def render_summary(rows: list[dict]) -> str:
    lines = ["", "### Summary"]
    for arm in ("ambient", "tool", "no-moss"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        n = len(arm_rows)
        searched = [r["moss_retrieval_ms"] for r in arm_rows if r["moss_retrieval_ms"] is not None]
        lines.append(f"**{arm}** ({n} queries)")
        lines.append(f"- hit: {sum(1 for r in arm_rows if r['hit'])}/{n}")
        lines.append(f"- faithful: {sum(1 for r in arm_rows if r['faithful'])}/{n}")
        if arm == "tool":
            lines.append(f"- tool_called: {sum(1 for r in arm_rows if r['tool_called'])}/{n}")
        if searched:
            lines.append(
                "- moss_retrieval_ms mean/p50/p95: "
                f"{format_ms(statistics.fmean(searched))} / "
                f"{format_ms(percentile(searched, 0.50))} / "
                f"{format_ms(percentile(searched, 0.95))}"
            )
        else:
            lines.append("- moss_retrieval_ms mean/p50/p95: n/a (no SDK timings)")
    return "\n".join(lines)


async def run_one(
    arm: str,
    query: str,
    gold: list[str],
    doc_id: str,
    session,
    queries: list[dict],
    docs: list[dict],
) -> dict:
    context = ""
    sdk_ms = None
    wall_ms = None
    tool_called = False

    if arm == "no-moss":
        answer = ""
    else:
        if arm == "tool":
            tool_called = True
        if session is not None:
            context, sdk_ms, wall_ms = await query_moss(session, query)
        else:
            context = lookup_faq(query, queries, docs)
        answer = context

    hit = contains_gold(context, gold)
    faithful = contains_gold(answer, gold)
    return {
        "id": doc_id,
        "query": query,
        "arm": arm,
        "moss_retrieval_ms": sdk_ms,
        "moss_wall_ms": wall_ms,
        "hit": bool(hit),
        "faithful": bool(faithful),
        "tool_called": tool_called,
        "answer": answer,
    }


async def run_bench(json_out: Path | None = None) -> list[dict]:
    queries = load_queries()
    docs = load_jsonl(KNOWLEDGE_PATH)
    session = await open_moss()
    if session is None:
        print(
            "note: no Moss session (set MOSS_PROJECT_ID / MOSS_PROJECT_KEY / "
            "MOSS_INDEX_NAME to measure moss_retrieval_ms). Using local FAQ lookup.",
            file=sys.stderr,
        )

    rows = []
    for row in queries:
        for arm in ("ambient", "tool", "no-moss"):
            rows.append(
                await run_one(
                    arm,
                    row["query"],
                    list(row["gold"]),
                    str(row["id"]),
                    session,
                    queries,
                    docs,
                )
            )

    print(render_table(rows))
    print(render_summary(rows))
    if json_out is not None:
        json_out.write_text(json.dumps(rows, indent=2) + "\n")
        print(f"\nwrote {json_out}")
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--echo-grounding",
        action="store_true",
        help="Zero-LLM smoke: ambient/tool answers are the retrieved block.",
    )
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    if not args.echo_grounding:
        raise SystemExit("pass --echo-grounding")
    asyncio.run(run_bench(json_out=args.json))


if __name__ == "__main__":
    main()
