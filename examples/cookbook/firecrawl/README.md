# Firecrawl + Moss Cookbook Example

Use Firecrawl to turn one or more URLs into clean markdown, then index the results into Moss and query them semantically from a notebook.

> This is a cookbook example, not a packaged integration. Open [firecrawl_moss.ipynb](firecrawl_moss.ipynb) to follow the full URL-to-query pipeline.

## Installation

```bash
pip install firecrawl-py moss python-dotenv
```

## Setup

Set these environment variables in your shell or a `.env` file:

```bash
FIRECRAWL_API_KEY=your-firecrawl-api-key
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
```

## Quick Start

1. Open [firecrawl_moss.ipynb](firecrawl_moss.ipynb) in Jupyter or VS Code.
2. Run the setup and helper cells.
3. Set `urls` to the pages you want to ingest.
4. Run `await build_and_query_knowledge_base(urls)` to crawl, index, and query the content.

## Workflow

The notebook is structured for efficiency:

1. **Prepare** (one-time): Crawl URLs → normalize markdown → index into Moss
2. **Query** (repeated): Run semantic queries against the indexed knowledge base without re-crawling

This design lets you crawl once (which can be slow/expensive) and then iterate on queries quickly.

## Architecture

```
┌─────────────┐
│   URLs      │
└──────┬──────┘
       │
       ├──> Firecrawl (crawl + scrape)
       │
┌──────▼─────────────────┐
│  Crawled Pages         │
│  (raw HTML/markdown)   │
└──────┬─────────────────┘
       │
       ├──> Markdown Normalization
       │    (clean text, remove chrome)
       │
┌──────▼─────────────────┐
│  Cleaned Markdown      │
│  (one DocumentInfo     │
│   per page)            │
└──────┬─────────────────┘
       │
       ├──> Moss Create Index
       │
┌──────▼─────────────────┐
│  Indexed Knowledge     │
│  Base (local or cloud) │
└──────┬─────────────────┘
       │
       ├──> Semantic Query (reusable)
       │    (no re-crawling needed)
       │
┌──────▼─────────────────┐
│  Top-K Results         │
│  (scored passages)     │
└─────────────────────────┘
```

## What the notebook does

```python
from firecrawl import Firecrawl
from moss import DocumentInfo, MossClient, QueryOptions

job = Firecrawl(api_key=FIRECRAWL_API_KEY).crawl(
	url="https://example.com",
	limit=3,
	scrape_options={"formats": ["markdown"]},
)

documents = [DocumentInfo(id="1", text=job.data[0].markdown, metadata={"source_url": "https://example.com"})]
await MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY).create_index("firecrawl-demo", documents)
```

## Files

| File | Description |
|------|-------------|
| `firecrawl_moss.ipynb` | Notebook that crawls URLs, indexes markdown into Moss, and runs semantic search |
