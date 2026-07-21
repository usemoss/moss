"""Create the demo Moss index the voice agent grounds on. Run once before bot.py."""

import asyncio
import os

from dotenv import load_dotenv
from loguru import logger
from moss import DocumentInfo, MossClient

load_dotenv()

DOCS = [
    ("kb-1", "Refunds are processed within 3-5 business days once the return is approved.", "billing"),
    ("kb-2", "You can track an order from the dashboard under Order History using its tracking number.", "orders"),
    ("kb-3", "Live chat support is available 24/7 from the Help menu in the app.", "support"),
    ("kb-4", "Standard shipping takes 3-5 business days; express shipping takes 1-2 business days.", "shipping"),
    ("kb-5", "Reset your password using the Forgot Password link on the login page.", "account"),
    ("kb-6", "We accept Visa, Mastercard, American Express, PayPal, and Apple Pay.", "billing"),
    ("kb-7", "Orders can be cancelled within 1 hour of placement, before they are dispatched.", "orders"),
    ("kb-8", "International shipping is available to most countries; rates and delivery times vary by destination.", "shipping"),
    ("kb-9", "Gift wrapping with a personalized message is available at checkout for a small fee.", "services"),
    ("kb-10", "We price-match identical items from authorized retailers within 14 days of purchase.", "billing"),
]


async def main():
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    index_name = os.environ["MOSS_INDEX_NAME"]
    docs = [DocumentInfo(id=i, text=t, metadata={"category": c}) for i, t, c in DOCS]
    logger.info(f"Creating index '{index_name}' with {len(docs)} documents...")
    await client.create_index(name=index_name, docs=docs, model_id="moss-minilm")
    logger.success(f"Index '{index_name}' created.")


if __name__ == "__main__":
    asyncio.run(main())
