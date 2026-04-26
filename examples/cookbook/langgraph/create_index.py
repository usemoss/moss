"""Create a small Moss index for the LangGraph cookbook example."""

from __future__ import annotations

import argparse
import asyncio
import os
import time

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_documents() -> list[DocumentInfo]:
    return [
        DocumentInfo(
            id="faq-returns-1",
            text="Refunds are processed within 3 to 5 business days after the returned item is received and inspected.",
            metadata={"category": "returns", "topic": "refund_timing"},
        ),
        DocumentInfo(
            id="faq-returns-2",
            text="Damaged products can be returned within 30 days of delivery with the original order number.",
            metadata={"category": "returns", "topic": "damaged_items"},
        ),
        DocumentInfo(
            id="faq-shipping-1",
            text="Standard shipping usually arrives within 5 to 7 business days for domestic orders.",
            metadata={"category": "shipping", "topic": "delivery_time"},
        ),
        DocumentInfo(
            id="faq-orders-1",
            text="Orders can be cancelled within 2 hours of purchase from the order history page.",
            metadata={"category": "orders", "topic": "cancellation"},
        ),
        DocumentInfo(
            id="faq-payment-1",
            text="We accept major credit cards, debit cards, and selected wallet-based payment methods.",
            metadata={"category": "payment", "topic": "methods"},
        ),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a demo Moss index for the LangGraph cookbook."
    )
    parser.add_argument(
        "--index-name",
        help="Optional index name. If omitted, a unique demo name is generated.",
    )
    args = parser.parse_args()

    project_id = _require_env("MOSS_PROJECT_ID")
    project_key = _require_env("MOSS_PROJECT_KEY")
    index_name = args.index_name or f"langgraph-demo-{int(time.time())}"

    client = MossClient(project_id, project_key)
    documents = _build_documents()

    print(f"Creating index '{index_name}' with {len(documents)} demo docs...")

    try:
        await client.create_index(index_name, documents)
        print("Index created successfully.\n")
    except RuntimeError as exc:
        if "already exists" not in str(exc):
            raise
        print("Index already exists. Reusing it.\n")

    print("Use this in examples/cookbook/langgraph/.env:")
    print(f"MOSS_INDEX_NAME={index_name}\n")

    print("Suggested live tests:")
    print(
        "python .\\examples\\cookbook\\langgraph\\moss_langgraph.py "
        '--question "What is the refund policy?"'
    )
    print(
        "python .\\examples\\cookbook\\langgraph\\moss_langgraph.py "
        '--question "What is the refund policy?" --filter-eq category=returns'
    )


if __name__ == "__main__":
    asyncio.run(main())
