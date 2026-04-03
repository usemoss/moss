# Benchmark: Moss vs Pinecone vs Qdrant vs ChromaDB

Reproducible end-to-end latency benchmarks for semantic search.
**All measurements include embedding generation time** — the full cost
a developer actually pays per query.

## What's being measured

Each benchmark times the complete query cycle:

| System | What happens per query |
|--------|----------------------|
| **Moss** | `client.query(index_name, "text")` — embedding + search in one call |
| **Pinecone** | Call embedding API → send vector to Pinecone cloud → get results |
| **Qdrant** | Call embedding API → search local Qdrant index → get results |
| **ChromaDB** | Call embedding API → search local Chroma collection → get results |

Moss bundles a built-in embedding model. Competitors require an external
embedding service (OpenAI, self-hosted, etc.).

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in credentials
cp .env.example .env
# Edit .env with your API keys

# 3. Run all benchmarks
python run_all.py

# Or run individually
python run_all.py moss
python run_all.py qdrant chroma
```

### Required credentials

| Benchmark | What you need |
|-----------|--------------|
| Moss | `MOSS_PROJECT_ID` + `MOSS_PROJECT_KEY` |
| Pinecone | `PINECONE_API_KEY` |
| Qdrant | Nothing (runs locally in-memory) |
| ChromaDB | Nothing (runs locally in-memory) |
| Embedding | `OPENAI_API_KEY` or a custom endpoint URL |

### Embedding provider

Competitors need an embedding service. Two options:

**Option A: OpenAI (default)**
Set `OPENAI_API_KEY` in `.env`. Uses `text-embedding-3-small` (1536 dims).
This is the most common production setup.

**Option B: Self-hosted on [Modal](https://modal.com/docs/examples/text_embeddings_inference)**
Deploy the embedding server:
```bash
pip install modal
modal deploy embedding_server/modal_app.py
```
Then set in `.env`:
```
EMBEDDING_PROVIDER=custom
EMBEDDING_ENDPOINT=https://your-app--embedding-server-model-embed.modal.run
EMBEDDING_DIMENSION=768
```

## Benchmark parameters

- **Documents**: 100,000 FAQ-style documents across 8 categories
- **Queries**: 15 diverse search queries
- **Warmup**: 3 rounds (excluded from measurements)
- **Measured**: 50 rounds x 15 queries = 750 measurements per system
- **top_k**: 5

## Pre-built 100k test index

To reproduce our benchmarks against the same 100,000 documents we used,
set these credentials in your `.env`:

```
MOSS_PROJECT_ID=398e0fcf-3ffd-413f-b93c-2d726fa714b5
MOSS_PROJECT_KEY=moss_bvetgOAqmdC8y2De9SXX6MVEqdvByK49
MOSS_INDEX_NAME=bench-builtin-100000-1_0_0b17
```

This index is pre-loaded with the full 100k FAQ document set so you can
skip ingestion and jump straight to querying.