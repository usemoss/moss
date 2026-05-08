import asyncio
import json
import os

from dotenv import load_dotenv
from moss import MossClient, DocumentInfo, QueryOptions, RerankOptions

load_dotenv()

INDEX_NAME = "rerank-demo-full"


async def setup_index(client):
    """Delete old index, create fresh one with all FAQ data."""
    faqs_path = os.path.join(os.path.dirname(__file__), "faqs.json")
    with open(faqs_path, "r") as f:
        faqs = json.load(f)

    docs = [
        DocumentInfo(
            id=faq["id"],
            text=faq["text"],
            metadata={k: str(v) for k, v in faq.get("metadata", {}).items()},
        )
        for faq in faqs
    ]

    print(f"Setting up index '{INDEX_NAME}'")
    try:
        await client.delete_index(INDEX_NAME)
        print("Deleted old index.")
    except Exception:
        pass

    await client.create_index(INDEX_NAME, docs)
    print("Index created.")

    await client.load_index(INDEX_NAME)
    print("Index loaded.\n")


async def main():
    client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))

    await setup_index(client)

    print("Without Reranking")
    results = await client.query(
        INDEX_NAME,
        "How to get discount?",
        QueryOptions(top_k=5, alpha=0.8),
    )
    for i, doc in enumerate(results.docs):
        print(f"  {i + 1}. [{doc.score:.3f}] {doc.text[:100]}...")

    print("\nWith Cohere Reranking")
    results = await client.query(
        INDEX_NAME,
        "How to get discount?",
        QueryOptions(
            top_k=10,
            alpha=0.8,
            rerank=RerankOptions(
                provider="cohere",
                api_key=os.getenv("COHERE_API_KEY"),
                top_n=5,
            ),
        ),
    )
    for i, doc in enumerate(results.docs):
        print(f"  {i + 1}. [{doc.score:.3f}] {doc.text[:100]}...")


if __name__ == "__main__":
    asyncio.run(main())
