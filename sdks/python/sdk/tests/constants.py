"""
Test constants for cloud API integration tests.
Uses python-dotenv package to load environment variables from .env file.
"""

import os
from uuid import uuid4

# Test credentials
TEST_PROJECT_ID = os.getenv("MOSS_TEST_PROJECT_ID", "test-project-id")
TEST_PROJECT_KEY = os.getenv("MOSS_TEST_PROJECT_KEY", "test-project-key")

HAS_REAL_CLOUD_CREDS = (
    bool(os.getenv("MOSS_TEST_PROJECT_ID"))
    and bool(os.getenv("MOSS_TEST_PROJECT_KEY"))
    and TEST_PROJECT_ID != "test-project-id"
    and TEST_PROJECT_KEY != "test-project-key"
)

CLOUD_CREDS_WARNING = (
    "Skipping cloud/E2E tests: set real MOSS_TEST_PROJECT_ID and "
    "MOSS_TEST_PROJECT_KEY environment variables to run full integration tests."
)

# Test model ID
TEST_MODEL_ID = "moss-minilm"


def generate_unique_index_name(prefix: str = "test-e2e") -> str:
    """Generate a unique index name using UUID to avoid conflicts."""
    return f"{prefix}-{uuid4().hex[:12]}"


TEST_DOCUMENTS = [
    {
        "id": "doc-1",
        "text": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
    },
    {
        "id": "doc-2",
        "text": "Natural language processing (NLP) is a branch of AI that helps computers understand, interpret and manipulate human language.",
    },
    {
        "id": "doc-3",
        "text": "Deep learning uses neural networks with multiple layers to model and understand complex patterns in data.",
    },
    {
        "id": "doc-4",
        "text": "Computer vision enables machines to interpret and understand visual information from the world around them.",
    },
    {
        "id": "doc-5",
        "text": "Reinforcement learning is a type of machine learning where an agent learns to make decisions by performing actions and receiving rewards.",
    },
]

ADDITIONAL_TEST_DOCUMENTS = [
    {
        "id": "doc-6",
        "text": "Data science combines statistics, programming, and domain expertise to extract insights from data.",
    },
    {
        "id": "doc-7",
        "text": "Cloud computing provides on-demand access to computing resources over the internet.",
    },
]

# Test queries for semantic search
TEST_QUERIES = [
    {
        "query": "AI and neural networks",
        "expected_relevant_docs": ["doc-1", "doc-2", "doc-3"],
    },
    {
        "query": "learning from rewards",
        "expected_relevant_docs": ["doc-5"],
    },
    {
        "query": "visual understanding",
        "expected_relevant_docs": ["doc-4"],
    },
]
