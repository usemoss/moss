#!/usr/bin/env python3
"""
Minimal HuggingFace → Moss Ingestion Demo
==========================================
Demonstrates basic dataset ingestion without querying or custom mappers.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Load credentials from .env
for candidate in (Path(__file__).parent / ".env", Path(__file__).parents[3] / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break

from moss_connector_huggingface import HuggingFaceDatasetConnector, ingest

MOSS_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_KEY = os.getenv("MOSS_PROJECT_KEY")

async def main():
    if not MOSS_ID or not MOSS_KEY:
        print("Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set in your environment or .env file.")
        sys.exit(1)

    index_name = f"hf-demo-{uuid.uuid4().hex[:6]}"
    print(f"Ingesting into index: {index_name}...")

    # Build HuggingFace connector using Auto Mode
    connector = HuggingFaceDatasetConnector(
        dataset_name="MongoDB/supply_chain_contracts_dataset_small",
        split="train",
        streaming=True,
        id_column="Contract Number",
        text_columns=["Goods Description", "Shipper", "Receiver"],
        metadata_columns=["Shipper", "Receiver", "Value"],
    )

    # Ingest directly into Moss
    result = await ingest(
        connector,
        project_id=MOSS_ID,
        project_key=MOSS_KEY,
        index_name=index_name
    )

    if result:
        print(f"✓ Successfully ingested {result.doc_count} documents!")
    else:
        print("✗ Ingestion failed or returned empty.")

if __name__ == "__main__":
    asyncio.run(main())
