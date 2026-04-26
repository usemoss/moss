"""LangGraph cookbook example using Moss as a retrieval node."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from moss import MossClient, QueryOptions

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SYSTEM_PROMPT = (
    "You are a grounded assistant. Answer the user's question only from the "
    "retrieved Moss context. If the context is missing or insufficient, say "
    "that clearly instead of making up facts."
)


class RetrievedDoc(TypedDict):
    """Minimal document shape stored in graph state after retrieval."""

    id: str
    text: str
    score: float
    metadata: dict[str, str]


class LangGraphMossState(TypedDict):
    """State shared across the LangGraph nodes."""

    query: str
    metadata_filter: NotRequired[dict[str, Any] | None]
    top_k: NotRequired[int]
    retrieval_results: NotRequired[list[RetrievedDoc]]
    retrieval_context: NotRequired[str]
    retrieval_time_ms: NotRequired[int | None]
    answer: NotRequired[str]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _parse_filter_eq(raw: str | None) -> dict[str, Any] | None:
    """Parse a simple equality filter in the form: field=value."""
    if not raw:
        return None

    if "=" not in raw:
        raise ValueError("--filter-eq must be in the form field=value (e.g. category=returns).")

    field, value = raw.split("=", 1)
    field = field.strip()
    value = value.strip()

    if not field or not value:
        raise ValueError("--filter-eq must be in the form field=value (e.g. category=returns).")

    return {"field": field, "condition": {"$eq": value}}


def _format_context(results: list[RetrievedDoc]) -> str:
    if not results:
        return "No relevant Moss results were returned."

    blocks: list[str] = []
    for idx, result in enumerate(results, start=1):
        metadata = json.dumps(result["metadata"], sort_keys=True)
        blocks.append(
            f"[{idx}] id={result['id']} score={result['score']:.3f} "
            f"metadata={metadata}\n{result['text']}"
        )
    return "\n\n".join(blocks)


def _message_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts).strip()

    return str(content)


async def load_index_before_graph_runs(client: MossClient, index_name: str) -> None:
    """Explicitly load the Moss index before the graph starts."""
    print(f"Loading Moss index '{index_name}' locally before the graph runs...")

    # Local load keeps query() on the in-memory hot path and enables filters.
    await client.load_index(index_name)

    print(
        "Local load complete. Retrieval now stays in-memory "
        "(~1-10ms) instead of cloud fallback (~100-500ms).\n"
    )


def build_moss_graph(
    client: MossClient,
    index_name: str,
    llm: ChatGroq,
):
    """Build a LangGraph graph with retrieve -> generate nodes."""

    async def retrieve(state: LangGraphMossState) -> dict[str, Any]:
        """Retrieve documents from Moss and write them back into graph state."""
        query = state["query"]
        metadata_filter = state.get("metadata_filter")
        top_k = state.get("top_k", 4)

        result = await client.query(
            index_name,
            query,
            QueryOptions(
                top_k=top_k,
                alpha=0.8,
                filter=metadata_filter,
            ),
        )

        retrieval_results: list[RetrievedDoc] = [
            {
                "id": doc.id,
                "text": doc.text,
                "score": doc.score,
                "metadata": doc.metadata or {},
            }
            for doc in result.docs
        ]

        return {
            "retrieval_results": retrieval_results,
            "retrieval_context": _format_context(retrieval_results),
            "retrieval_time_ms": result.time_taken_ms,
        }

    async def generate(state: LangGraphMossState) -> dict[str, str]:
        """Generate a grounded answer from retrieved Moss context."""
        response = await llm.ainvoke(
            [
                ("system", SYSTEM_PROMPT),
                (
                    "human",
                    "Question:\n"
                    f"{state['query']}\n\n"
                    "Retrieved Moss context:\n"
                    f"{state.get('retrieval_context', 'No retrieval context available.')}",
                ),
            ]
        )

        return {"answer": _message_to_text(response.content)}

    graph = StateGraph(LangGraphMossState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


async def ask_question(
    graph: Any,
    user_question: str,
    metadata_filter: dict[str, Any] | None,
    top_k: int,
) -> LangGraphMossState:
    """Run a single LangGraph invocation."""
    result = await graph.ainvoke(
        {
            "query": user_question,
            "metadata_filter": metadata_filter,
            "top_k": top_k,
        }
    )
    return result


def _print_response(result: LangGraphMossState) -> None:
    docs = result.get("retrieval_results", [])
    time_taken_ms = result.get("retrieval_time_ms")
    latency = f"{time_taken_ms}ms" if time_taken_ms is not None else "unknown time"

    print(f"\n[Moss returned {len(docs)} docs in {latency}]")
    if docs:
        for doc in docs:
            print(f"- {doc['id']} (score={doc['score']:.3f})")
    print(f"\nAssistant: {result.get('answer', 'No answer generated.')}\n")


async def run_langgraph_agent(
    question: str | None = None,
    filter_eq: str | None = None,
    top_k: int = 4,
) -> None:
    """Run the LangGraph example in single-shot or interactive mode."""
    project_id = _require_env("MOSS_PROJECT_ID")
    project_key = _require_env("MOSS_PROJECT_KEY")
    index_name = _require_env("MOSS_INDEX_NAME")
    groq_api_key = _require_env("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    client = MossClient(project_id, project_key)
    await load_index_before_graph_runs(client, index_name)

    llm = ChatGroq(model=model, api_key=groq_api_key, temperature=0)
    graph = build_moss_graph(client, index_name, llm)

    if question:
        metadata_filter = _parse_filter_eq(filter_eq)
        result = await ask_question(
            graph,
            user_question=question,
            metadata_filter=metadata_filter,
            top_k=top_k,
        )
        _print_response(result)
        return

    print("=== Moss + LangGraph Grounded Agent ===")
    print("Each turn runs: question -> retrieve node -> generate node")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_question:
            continue
        if user_question.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        raw_filter = input(
            "Metadata filter (optional, field=value): "
        ).strip()

        try:
            metadata_filter = _parse_filter_eq(raw_filter or None)
            result = await ask_question(
                graph,
                user_question=user_question,
                metadata_filter=metadata_filter,
                top_k=top_k,
            )
            _print_response(result)
        except Exception as exc:
            print(f"\nError: {exc}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LangGraph cookbook example using Moss as a retrieval node."
    )
    parser.add_argument(
        "--question",
        help="Single question to answer. Omit for interactive mode.",
    )
    parser.add_argument(
        "--filter-eq",
        help="Optional convenience filter in the form field=value (e.g. category=returns).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=4,
        help="Number of Moss results to retrieve per question.",
    )
    args = parser.parse_args()

    asyncio.run(
        run_langgraph_agent(
            question=args.question,
            filter_eq=args.filter_eq,
            top_k=args.top_k,
        )
    )


if __name__ == "__main__":
    main()
