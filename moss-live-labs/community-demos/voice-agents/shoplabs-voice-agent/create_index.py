import asyncio
import os

from dotenv import load_dotenv
from loguru import logger
from moss import DocumentInfo, MossClient

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def upload_documents() -> None:
    """Create a small ecommerce support index for the demo agent."""
    client = MossClient(
        project_id=_require_env("MOSS_PROJECT_ID"),
        project_key=_require_env("MOSS_PROJECT_KEY"),
    )
    index_name = _require_env("MOSS_INDEX_NAME")

    docs = [
        DocumentInfo(
            id="refund-policy",
            text=(
                "Refund policy: Customers can request a refund within 30 days of delivery. "
                "Approved refunds are processed to the original payment method within 3 to 5 business days."
            ),
            metadata={"topic": "refunds"},
        ),
        DocumentInfo(
            id="shipping-times",
            text=(
                "Shipping policy: Standard shipping takes 3 to 5 business days. Express shipping "
                "takes 1 to 2 business days. International shipping times vary by destination."
            ),
            metadata={"topic": "shipping"},
        ),
        DocumentInfo(
            id="order-tracking",
            text=(
                "Order tracking: Customers can track orders from the Order History page. "
                "A tracking link is also sent by email once the order ships."
            ),
            metadata={"topic": "orders"},
        ),
        DocumentInfo(
            id="cancel-order",
            text=(
                "Order cancellation: Orders can be cancelled within 1 hour of placement. "
                "After that, customers must contact support and cancellation is only possible if the order has not shipped."
            ),
            metadata={"topic": "orders"},
        ),
        DocumentInfo(
            id="password-reset",
            text=(
                "Account access: To reset a password, click Forgot Password on the sign-in page. "
                "A reset link is then sent to the customer's email address."
            ),
            metadata={"topic": "account"},
        ),
        DocumentInfo(
            id="product-moisturizer",
            text=(
                "Product recommendation: The CloudSoft Moisturizer is best for dry and sensitive skin. "
                "It contains ceramides, hyaluronic acid, and fragrance-free hydration."
            ),
            metadata={"topic": "products"},
        ),
        DocumentInfo(
            id="product-cleanser",
            text=(
                "Product recommendation: The Balance Gel Cleanser is best for oily or acne-prone skin. "
                "It removes excess oil without stripping the skin barrier."
            ),
            metadata={"topic": "products"},
        ),
        DocumentInfo(
            id="abandoned-cart",
            text=(
                "Abandoned cart support: If a customer leaves checkout because shipping feels expensive, "
                "support should explain delivery options and available free-shipping thresholds."
            ),
            metadata={"topic": "checkout"},
        ),
    ]

    try:
        logger.info("Creating Moss index '{}'", index_name)
        await client.create_index(index_name, docs)
        logger.success("Created index '{}' with {} documents", index_name, len(docs))
    except Exception as exc:
        logger.error("Failed to create index '{}': {}", index_name, exc)
        raise


if __name__ == "__main__":
    asyncio.run(upload_documents())
