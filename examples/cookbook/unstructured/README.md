# Unstructured + Moss Cookbook

Parse PDFs, Word docs, HTML, images, and other file formats with [Unstructured](https://unstructured.io/) and index the extracted content into [Moss](https://moss.dev) for semantic search.

This cookbook shows a focused ingestion pipeline:

1. Partition raw files with Unstructured
2. Chunk extracted elements
3. Preserve source metadata on every chunk
4. Upsert chunks into a Moss index with stable document IDs
5. Query the loaded Moss index

## Setup

```bash
cd examples/cookbook/unstructured
uv sync
cp .env.example .env
```

Fill in `.env` with your Moss credentials:

```bash
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=unstructured-docs
```

## Usage

Index the sample documents:

```bash
uv run python ingest.py --input-dir sample_docs
```

Index your own folder:

```bash
uv run python ingest.py --input-dir /path/to/files --index-name company-docs
```

Ask a query after ingestion:

```bash
uv run python ingest.py \
  --input-dir sample_docs \
  --query "What does the onboarding policy say about access?"
```

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
