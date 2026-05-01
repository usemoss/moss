"""Core LangGraph + Moss integration helpers for the cookbook example."""

from __future__ import annotations

import json
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from moss import MossClient, QueryOptions, SearchResult

SYSTEM_PROMPT = (
    "You are a grounded assistant. Answer the user's question only from the "
    "retrieved Moss context. If the context is missing or insufficient, say "
    "that clearly instead of making up facts."
)


class LangGraphMossState(TypedDict):
    """State shared across the LangGraph nodes."""

    query: str
    metadata_filter: NotRequired[dict[str, Any] | None]
    top_k: NotRequired[int]
    alpha: NotRequired[float | None]
    retrieval_results: NotRequired[SearchResult]
    retrieval_context: NotRequired[str]
    retrieval_time_ms: NotRequired[int | None]
    answer: NotRequired[str]


def _format_context(result: SearchResult) -> str:
    if not result.docs:
        return "No relevant Moss results were returned."

    blocks: list[str] = []
    for idx, doc in enumerate(result.docs, start=1):
        metadata = json.dumps(doc.metadata or {}, sort_keys=True)
        blocks.append(
            f"[{idx}] id={doc.id} score={doc.score:.3f} "
            f"metadata={metadata}\n{doc.text}"
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


def build_moss_graph(
    client: MossClient,
    index_name: str,
    llm: Any,
):
    """Build a LangGraph graph with retrieve -> generate nodes."""

    async def retrieve(state: LangGraphMossState) -> dict[str, Any]:
        """Retrieve documents from Moss and write them back into graph state."""
        query = state["query"]
        metadata_filter = state.get("metadata_filter")
        top_k = state.get("top_k", 4)
        alpha = state.get("alpha")

        result = await client.query(
            index_name,
            query,
            QueryOptions(
                top_k=top_k,
                alpha=alpha,
                filter=metadata_filter,
            ),
        )

        return {
            "retrieval_results": result,
            "retrieval_context": _format_context(result),
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
    alpha: float | None,
) -> LangGraphMossState:
    """Run a single LangGraph invocation."""
    result = await graph.ainvoke(
        {
            "query": user_question,
            "metadata_filter": metadata_filter,
            "top_k": top_k,
            "alpha": alpha,
        }
    )
    return result
