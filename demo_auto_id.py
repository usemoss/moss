#!/usr/bin/env python3
"""
Demo script for auto_id feature in Moss connectors.

This script:
1. Runs the unit tests for auto_id.
2. Performs a live ingest with auto_id=True into your existing 'demo-customer_faqs' index.
3. Queries the index to show documents with UUID IDs.

Requirements:
- Moss project_id and project_key set in .env file.
- moss and moss-connector-sqlite installed.
- pytest for running tests.
"""

import asyncio
import os
from typing import Iterable
from dotenv import load_dotenv

from moss import DocumentInfo, MossClient
from moss_connector_sqlite import ingest


async def run_demo():
    # Load environment variables from .env
    load_dotenv()
    # Step 1: Run unit tests
    print("=== Running Unit Tests ===")
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest",
        "packages/moss-data-connector/moss-connector-sqlite/tests/test_sqlite.py::test_auto_id_defaults_to_false",
        "packages/moss-data-connector/moss-connector-sqlite/tests/test_sqlite.py::test_auto_id_replaces_mapper_id",
        "-v"
    ], capture_output=True, text=True, cwd="/home/arm8tron/moss")
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    print("Tests completed.\n")

    # Step 2: Live ingest with auto_id=True
    print("=== Live Ingest with auto_id=True ===")

    # Get credentials from environment
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        print("Error: Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env file.")
        return

    client = MossClient(project_id, project_key)

    # Sample data mimicking rows without IDs (e.g., from API or CSV)
    sample_data = [
        {"question": "How do I reset my password?", "answer": "Go to settings and click reset."},
        {"question": "What are your support hours?", "answer": "24/7 via chat."},
        {"question": "How to cancel my subscription?", "answer": "Contact support or use the dashboard."},
    ]

    # Create a simple iterable source (no DB needed)
    def sample_source() -> Iterable[DocumentInfo]:
        for row in sample_data:
            yield DocumentInfo(
                id="",  # Empty ID, will be replaced by auto_id=True
                text=f"Q: {row['question']} A: {row['answer']}",
                metadata={"type": "faq", "question": row["question"]},
            )

    print(f"Ingesting {len(sample_data)} documents into 'demo' with auto_id=True...")

    source = sample_source()
    result = await ingest(
        source,
        project_id=project_id,
        project_key=project_key,
        index_name="demo",
        auto_id=True,
    )
    print(f"Ingest result: {result}")

    # Step 3: Query and show UUID IDs
    print("\n=== Querying Index to Show UUID IDs ===")
    docs = await client.get_docs("demo")
    print(f"Total documents in index: {len(docs)}")
    print("Last 3 documents (showing UUID IDs):")
    for doc in docs[-3:]:
        print(f"  ID: {doc.id} | Text: {doc.text[:50]}...")

    print("\nDemo completed")


if __name__ == "__main__":
    asyncio.run(run_demo())