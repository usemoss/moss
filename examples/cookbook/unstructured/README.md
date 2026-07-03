# Unstructured + Moss Cookbook

Parse PDFs, Word docs, HTML, images, and other file formats with [Unstructured](https://unstructured.io/) and index the extracted content into [Moss](https://moss.dev) for semantic search.

This cookbook shows a focused ingestion pipeline:

1. Partition raw files with Unstructured
2. Chunk extracted elements
3. Preserve source metadata on every chunk
4. Upsert chunks into a Moss index with stable document IDs
5. Query the loaded Moss index

## Setup

Python 3.11 or newer is required. From the repository root:

```bash
cd examples/cookbook/unstructured
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

If you already use [uv](https://docs.astral.sh/uv/), `uv sync` can replace the
virtual-environment and `pip install` commands above.

Fill in `.env` with your Moss credentials:

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=unstructured-docs
```

## Usage

Index the sample documents:

```bash
python ingest.py --input-dir sample_docs
```

Index your own folder:

```bash
python ingest.py --input-dir /path/to/files --index-name company-docs
```

Ask a query after ingestion:

```bash
python ingest.py \
  --input-dir sample_docs \
  --query "What does the onboarding policy say about access?"
```

The command runs the complete pipeline against Moss: it partitions and chunks each
source file, creates or incrementally updates the index, waits for every ingestion
job to complete, loads the finished index, and runs the query. A successful run
prints each stage, for example:

```text
Parsed onboarding.html -> 1 chunks
Parsed release-notes.txt -> 1 chunks

Prepared 2 chunks from .../sample_docs
Created index 'unstructured-docs' with 2 chunks
Job <job-id> completed

Query: What does the onboarding policy say about access?
1. onboarding.html (score=...)
New hires receive repository access after completing security training...
```

Rerun the same command to demonstrate incremental ingestion. The second run reports
that the index already exists and upserts the stable chunk IDs instead of creating
duplicates.

## What Gets Stored

Each Moss document is one Unstructured chunk:

```python
DocumentInfo(
    id="docs/handbook.pdf::chunk-0003",
    text="Extracted chunk text...",
    metadata={
        "source_path": "docs/handbook.pdf",
        "filename": "handbook.pdf",
        "filetype": ".pdf",
        "chunk_index": "3",
        "category": "CompositeElement",
        "page_number": "4",
        "text_hash": "a1b2c3d4e5f6",
    },
)
```

Chunk IDs are deterministic from the relative file path and chunk index. Rerunning the same ingestion uses `MutationOptions(upsert=True)`, so chunks are updated in place.
