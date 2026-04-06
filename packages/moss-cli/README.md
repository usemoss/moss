# Moss CLI

**Command-line interface for Moss semantic search** — manage indexes, documents, and queries directly from your terminal.

Moss CLI wraps the [Moss Python SDK](https://docs.moss.dev/) so you can build and query semantic search indexes without writing any code. Ideal for quick prototyping, scripting, CI/CD pipelines, and data workflows.

## Features

- **Full SDK coverage** — every SDK operation available as a CLI command
- **Semantic search** — query indexes with configurable hybrid search (semantic + keyword)
- **Index management** — create, list, inspect, and delete indexes
- **Document management** — add, update, retrieve, and delete documents
- **Local by default** — downloads indexes for on-device queries, `--cloud` to skip
- **Flexible auth** — CLI flags, environment variables, or config file
- **Multiple output formats** — rich tables for humans, `--json` for scripts
- **Job tracking** — poll background jobs with live progress display
- **Pipe-friendly** — stdin/stdout support for composing with other tools

## Installation

```bash
pip install moss-cli
```

## Quick Start

```bash
# 1. Save your credentials
moss init

# 2. List your indexes
moss index list

# 3. Create an index from a JSON file
moss index create my-index -f docs.json --wait

# 4. Search it
moss query my-index "what is machine learning"

# 5. Search via cloud API (skips local download)
moss query my-index "neural networks" --cloud
```

## Authentication

Credentials are resolved in this order:

1. **CLI flags**: `--project-id` and `--project-key`
2. **Environment variables**: `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY`
3. **Config file**: `~/.moss/config.json` (created by `moss init`)

```bash
# Option 1: Interactive setup (recommended)
moss init

# Option 2: Environment variables
export MOSS_PROJECT_ID="your-project-id"
export MOSS_PROJECT_KEY="your-project-key"

# Option 3: Inline flags
moss index list --project-id "..." --project-key "..."
```

## Commands

### Index Management

```bash
# Create an index with documents from a JSON file
moss index create my-index -f documents.json --model moss-minilm

# Create and wait for completion
moss index create my-index -f documents.json --wait

# List all indexes
moss index list

# Get index details
moss index get my-index

# Delete an index
moss index delete my-index
moss index delete my-index --confirm  # skip prompt
```

### Document Management

```bash
# Add documents to an existing index
moss doc add my-index -f new-docs.json

# Add with upsert (update existing, insert new)
moss doc add my-index -f docs.json --upsert --wait

# Get all documents
moss doc get my-index

# Get specific documents
moss doc get my-index --ids doc1,doc2,doc3

# Delete documents
moss doc delete my-index --ids doc1,doc2
```

### Query

```bash
# Search (downloads index and queries on-device by default)
moss query my-index "what is deep learning"

# Tune results: more results, keyword-heavy
moss query my-index "neural networks" --top-k 20 --alpha 0.3

# Cloud mode (skip download, query via cloud API)
moss query my-index "transformers" --cloud

# With metadata filter (local only)
moss query my-index "shoes" --filter '{"field": "category", "condition": {"$eq": "footwear"}}'

# Pipe query from stdin
echo "what is AI" | moss query my-index

# JSON output for scripting
moss query my-index "query" --json | jq '.docs[0].text'
```

### Job Tracking

```bash
# Check job status
moss job status <job-id>

# Wait for job to finish (with live progress)
moss job status <job-id> --wait
```

### Other

```bash
# Print version info
moss version

# Global JSON output
moss index list --json
moss doc get my-index --json
```

## Document File Format

### JSON (recommended)

```json
[
  {"id": "doc1", "text": "Machine learning fundamentals", "metadata": {"topic": "ml"}},
  {"id": "doc2", "text": "Deep learning with neural networks"},
  {"id": "doc3", "text": "Natural language processing", "metadata": {"topic": "nlp"}}
]
```

Also supports a wrapper format: `{"documents": [...]}`.

### CSV

```csv
id,text,metadata
doc1,Machine learning fundamentals,"{""topic"": ""ml""}"
doc2,Deep learning with neural networks,
doc3,Natural language processing,"{""topic"": ""nlp""}"
```

### stdin

```bash
cat docs.json | moss index create my-index -f -
cat docs.json | moss doc add my-index -f -
```

## Global Options

| Flag | Short | Description |
|---|---|---|
| `--project-id` | `-p` | Project ID (overrides env/config) |
| `--project-key` | | Project key (overrides env/config) |
| `--json` | | Machine-readable JSON output |
| `--verbose` | `-v` | Enable debug logging |

## Available Models

| Model | Description |
|---|---|
| `moss-minilm` | Lightweight, optimized for speed (default) |
| `moss-mediumlm` | Balanced accuracy and performance |
| `custom` | Used automatically when documents include embeddings |

## License

Copyright (c) 2026 InferEdge Inc. — BSD 2-Clause License.

See [LICENSE](LICENSE) for full terms.
