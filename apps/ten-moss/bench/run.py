"""Offline gold-phrase bench: ambient vs tool-call vs no-Moss.

No mic, no Agora, no Deepgram. --echo-grounding needs no cloud LLM key.

    python bench/run.py --echo-grounding

With Moss credentials the ambient/tool arms query MossSessionManager.
Without them, --echo-grounding still prints the table using a local
substring lookup over data/knowledge.jsonl (moss_retrieval_ms is then n/a).
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
from typing import Any, Callable, Awaitable

HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parent
QUERIES_PATH = HERE / "queries.jsonl"
KNOWLEDGE_PATH = APP_DIR / "data" / "knowledge.jsonl"

ARMS = ("ambient", "tool", "no-moss")
SearchFn = Callable[[str], Awaitable[tuple[str, float | None, float | None]]]


def load_queries(path: Path = QUERIES_PATH) -> list[dict[str, Any]]:
    """Load the published 10-query gold file."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def load_knowledge(path: Path = KNOWLEDGE_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def contains_gold(text: str, gold: list[str]) -> bool:
    """True if any gold key-phrase is a substring of text."""
    haystack = text or ""
    return any(phrase in haystack for phrase in gold)


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    frac = k - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


class LocalCorpusSearch:
    """Pair each published query with its FAQ so --echo-grounding works without Moss keys."""

    def __init__(self, docs: list[dict[str, Any]], queries: list[dict[str, Any]]):
        self.docs = {str(d.get("id")): d for d in docs}
        self.query_to_id = {str(q.get("query")): str(q.get("id")) for q in queries}

    async def search(self, query: str) -> tuple[str, float | None, float | None]:
        doc_id = self.query_to_id.get(query)
        doc = self.docs.get(doc_id) if doc_id else None
        if doc is None:
            return "", None, None
        block = (
            "Relevant knowledge from Moss:\n\n"
            f"[1] {doc.get('text', '')}"
        )
        return block, None, None


class MossSearch:
    def __init__(self, session: Any):
        self.session = session

    async def search(self, query: str) -> tuple[str, float | None, float | None]:
        t0 = time.perf_counter()
        try:
            context = await self.session.query_context(query)
        except Exception:  # noqa: BLE001 - fail open
            return "", None, (time.perf_counter() - t0) * 1000.0
        wall_ms = (time.perf_counter() - t0) * 1000.0
        sdk_ms = getattr(self.session, "last_time_taken_ms", None)
        if sdk_ms is not None:
            sdk_ms = float(sdk_ms)
        return context or "", sdk_ms, wall_ms


async def echo_answer(
    *,
    arm: str,
    query: str,
    search: SearchFn | None,
    always_call_tool: bool,
) -> dict[str, Any]:
    """Zero-LLM arm: ambient/tool echo the retrieved block; no-Moss answers empty."""
    tool_called = False
    context = ""
    sdk_ms: float | None = None
    wall_ms: float | None = None
    if arm == "no-moss":
        answer = ""
    elif arm == "tool":
        # Stub: --echo-grounding has no model, so the tool arm always searches.
        tool_called = always_call_tool
        if tool_called and search is not None:
            context, sdk_ms, wall_ms = await search(query)
        answer = context
    else:
        if search is not None:
            context, sdk_ms, wall_ms = await search(query)
        answer = context
    return {
        "context": context,
        "answer": answer,
        "moss_retrieval_ms": sdk_ms,
        "moss_wall_ms": wall_ms,
        "tool_called": tool_called,
    }


def score_row(query_row: dict[str, Any], result: dict[str, Any], arm: str) -> dict[str, Any]:
    gold = list(query_row["gold"])
    context = result.get("context") or ""
    answer = result.get("answer") or ""
    doc_id = str(query_row.get("id") or "")
    hit = contains_gold(context, gold) or (doc_id and doc_id in context)
    faithful = contains_gold(answer, gold)
    return {
        "id": query_row["id"],
        "query": query_row["query"],
        "arm": arm,
        "moss_retrieval_ms": result.get("moss_retrieval_ms"),
        "moss_wall_ms": result.get("moss_wall_ms"),
        "hit": bool(hit),
        "faithful": bool(faithful),
        "tool_called": bool(result.get("tool_called")),
        "answer": answer,
    }


def render_table(rows: list[dict[str, Any]]) -> str:
    header = (
        "| query | arm | moss_retrieval_ms | moss_wall_ms | hit | faithful | tool_called |"
    )
    sep = "| --- | --- | ---: | ---: | --- | --- | --- |"
    lines = [header, sep]
    for row in rows:
        lines.append(
            "| {query} | {arm} | {retr} | {wall} | {hit} | {faithful} | {tool} |".format(
                query=row["query"],
                arm=row["arm"],
                retr=format_ms(row["moss_retrieval_ms"]),
                wall=format_ms(row["moss_wall_ms"]),
                hit=_yes(row["hit"]),
                faithful=_yes(row["faithful"]),
                tool=_yes(row["tool_called"]) if row["arm"] == "tool" else "-",
            )
        )
    return "\n".join(lines)


def render_summary(rows: list[dict[str, Any]]) -> str:
    lines = ["", "### Summary"]
    for arm in ARMS:
        arm_rows = [r for r in rows if r["arm"] == arm]
        searched = [
            r["moss_retrieval_ms"]
            for r in arm_rows
            if r["moss_retrieval_ms"] is not None
        ]
        n = len(arm_rows)
        faithful = sum(1 for r in arm_rows if r["faithful"])
        hits = sum(1 for r in arm_rows if r["hit"])
        tool_called = sum(1 for r in arm_rows if r["tool_called"])
        lines.append(f"**{arm}** ({n} queries)")
        lines.append(f"- hit: {hits}/{n}")
        lines.append(f"- faithful: {faithful}/{n}")
        if arm == "tool":
            lines.append(f"- tool_called: {tool_called}/{n}")
        if searched:
            mean = statistics.fmean(searched)
            p50 = percentile(searched, 0.50)
            p95 = percentile(searched, 0.95)
            lines.append(
                f"- moss_retrieval_ms mean/p50/p95: "
                f"{format_ms(mean)} / {format_ms(p50)} / {format_ms(p95)}"
            )
        else:
            lines.append("- moss_retrieval_ms mean/p50/p95: n/a (no SDK timings)")
    return "\n".join(lines)


async def open_moss_search() -> MossSearch | None:
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
    except Exception as exc:  # noqa: BLE001
        print(f"warning: Moss session failed to open ({exc}); using local corpus", file=sys.stderr)
        return None
    return MossSearch(session)


async def run_bench(*, echo_grounding: bool, json_out: Path | None) -> list[dict[str, Any]]:
    if not echo_grounding:
        raise SystemExit("This slice ships --echo-grounding only. A live LLM arm is follow-up.")
    queries = load_queries()
    moss = await open_moss_search()
    if moss is not None:
        search: SearchFn = moss.search
        backend = "moss"
    else:
        search = LocalCorpusSearch(load_knowledge(), queries).search
        backend = "local-corpus"
        print(
            "note: no Moss session (set MOSS_PROJECT_ID / MOSS_PROJECT_KEY / "
            "MOSS_INDEX_NAME to measure moss_retrieval_ms). Using local corpus.",
            file=sys.stderr,
        )

    rows: list[dict[str, Any]] = []
    for query_row in queries:
        for arm in ARMS:
            result = await echo_answer(
                arm=arm,
                query=query_row["query"],
                search=search,
                always_call_tool=True,
            )
            scored = score_row(query_row, result, arm)
            scored["backend"] = backend
            rows.append(scored)

    table = render_table(rows)
    summary = render_summary(rows)
    print(table)
    print(summary)
    if json_out is not None:
        json_out.write_text(json.dumps(rows, indent=2) + "\n")
        print(f"\nwrote {json_out}")
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--echo-grounding",
        action="store_true",
        help="Zero-LLM smoke: ambient/tool answers are the retrieved block.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional path to write the per-row JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.echo_grounding:
        raise SystemExit("pass --echo-grounding (zero-LLM smoke is the required gate)")
    asyncio.run(run_bench(echo_grounding=True, json_out=args.json))


if __name__ == "__main__":
    main()
