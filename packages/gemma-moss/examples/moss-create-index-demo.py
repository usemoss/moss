"""One-time setup: create a Moss index with sample FAQ documents.

Prerequisites:
    pip install gemma-moss python-dotenv

Environment variables:
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME
"""

import asyncio
import os

from dotenv import load_dotenv

from gemma_moss import DocumentInfo, MossClient

load_dotenv()


async def main():
    """Create a sample FAQ index in Moss."""
    client = MossClient(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
    )

    documents = [
        DocumentInfo(
            id="doc-1",
            text=(
                "How do I track my order? You can track your order by logging into "
                "your account and visiting the 'Order History' section. Each order has "
                "a unique tracking number that you can use to monitor its delivery status."
            ),
            metadata={"category": "orders", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-2",
            text=(
                "What is your return policy? We offer a 30-day return policy for most "
                "items. Products must be unused and in their original packaging. Return "
                "shipping costs may apply unless the item is defective."
            ),
            metadata={"category": "returns", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-3",
            text=(
                "How can I change my shipping address? You can change your shipping "
                "address before order dispatch by contacting our customer service team. "
                "Once an order is dispatched, the shipping address cannot be modified."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-4",
            text=(
                "Do you ship internationally? Yes, we ship to most countries worldwide. "
                "International shipping costs and delivery times vary by location. You "
                "can check shipping rates during checkout."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-5",
            text=(
                "What payment methods do you accept? We accept Visa, Mastercard, "
                "American Express, PayPal, and Apple Pay. All payments are processed "
                "securely through our encrypted payment system."
            ),
            metadata={"category": "payment", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-6",
            text=(
                "How long does shipping take? Standard domestic shipping typically "
                "takes 3-5 business days. Express shipping (1-2 business days) is "
                "available for most locations at an additional cost."
            ),
            metadata={"category": "shipping", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-7",
            text=(
                "Can I cancel my order? Orders can be cancelled within 1 hour of "
                "placement. After that, if the order has not been shipped, you may "
                "contact customer service to request cancellation."
            ),
            metadata={"category": "orders", "source": "faq"},
        ),
        DocumentInfo(
            id="doc-8",
            text=(
                "What is your price match policy? We match prices from authorized "
                "retailers for identical items within 14 days of purchase. Send us "
                "proof of the lower price, and we'll refund the difference."
            ),
            metadata={"category": "pricing", "source": "faq"},
        ),
    ]

    print(f"Creating index '{os.getenv('MOSS_INDEX_NAME')}' with {len(documents)} documents...")
    result = await client.create_index(
        name=os.getenv("MOSS_INDEX_NAME"),
        docs=documents,
        model_id="moss-minilm",
    )
    print(f"Index created. Job ID: {result.job_id}")


if __name__ == "__main__":
    asyncio.run(main())
