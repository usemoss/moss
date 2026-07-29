"""Create and populate a demo Moss index for the ten-moss integration.

Usage:
    export MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... MOSS_INDEX_NAME=...
    python examples/create_index.py
"""

import asyncio
import os

from loguru import logger
from moss import DocumentInfo, MossClient

try:  # python-dotenv is optional; the script also works with real env vars.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when python-dotenv isn't installed

    def load_dotenv(*args, **kwargs):
        """No-op fallback when python-dotenv is not installed."""
        return False


def build_documents() -> list[DocumentInfo]:
    """Return a small support knowledge base for the demo index."""
    return [
        DocumentInfo(
            id="doc-1",
            text="Refunds are processed within 3-5 business days once approved.",
            metadata={"category": "billing"},
        ),
        DocumentInfo(
            id="doc-2",
            text="You can track your order from the dashboard under Order History.",
            metadata={"category": "orders"},
        ),
        DocumentInfo(
            id="doc-3",
            text="We offer 24/7 live chat support from the Help menu.",
            metadata={"category": "support"},
        ),
        DocumentInfo(
            id="doc-4",
            text="Standard shipping takes 3-5 business days; express takes 1-2.",
            metadata={"category": "shipping"},
        ),
        DocumentInfo(
            id="doc-5",
            text="Reset your password using the Forgot Password link on the login page.",
            metadata={"category": "account"},
        ),
        DocumentInfo(
            id="doc-6",
            text="We accept Visa, Mastercard, American Express, PayPal, and Apple Pay.",
            metadata={"category": "billing"},
        ),
        DocumentInfo(
            id="doc-7",
            text="Orders can be cancelled within 1 hour of placement.",
            metadata={"category": "orders"},
        ),
        DocumentInfo(
            id="doc-8",
            text="International shipping is available to most countries; rates vary.",
            metadata={"category": "shipping"},
        ),
        DocumentInfo(
            id="doc-9",
            text="Gift wrapping is available at checkout for a small fee.",
            metadata={"category": "services"},
        ),
        DocumentInfo(
            id="doc-10",
            text="We price-match authorized retailers within 14 days of purchase.",
            metadata={"category": "billing"},
        ),
    ]


async def main() -> None:
    """Create the index named by MOSS_INDEX_NAME from build_documents()."""
    load_dotenv()
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    index_name = os.environ["MOSS_INDEX_NAME"]
    logger.info("Creating index {}", index_name)
    await client.create_index(name=index_name, docs=build_documents(), model_id="moss-minilm")
    logger.success("Index {} created", index_name)


if __name__ == "__main__":
    asyncio.run(main())
