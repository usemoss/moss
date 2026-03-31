# Moss Docker Example

Dockerized example showing how to use the Moss Python and JS SDKs inside containers — the same pattern used in AWS ECS, Kubernetes, and other container runtimes.

## Structure

```
apps/docker/
├── docker-compose.yml      # Runs both examples together
├── .env.example            # Environment variable template
├── python/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py             # Loads an index and runs a query
└── javascript/
    ├── Dockerfile
    ├── package.json
    └── main.ts             # Loads an index and runs a query
```

## Setup

**1. Configure credentials**

Get your project credentials from the [Moss Portal](https://portal.usemoss.dev).

```bash
cp .env.example .env
```

Fill in `.env`:

```
MOSS_PROJECT_ID=your_project_id
MOSS_PROJECT_KEY=your_project_key
MOSS_INDEX_NAME=your_index_name   # must already exist
```

> The index must already exist. Use the [Python](../../examples/python/) or [JS](../../examples/javascript/) examples to create one first.

**2. Run with Docker Compose**

```bash
docker compose up --build
```

This builds and runs both the Python and JavaScript containers. Each loads the configured index and runs a sample query.

**Run just one:**

```bash
docker compose up --build python-app
docker compose up --build javascript-app
```

## How it works

Both examples follow the same pattern:

1. Read credentials from environment variables (injected by Docker)
2. Initialize `MossClient(projectId, projectKey)`
3. Call `loadIndex(indexName)` to load the index into memory
4. Call `query(indexName, text, { topK: 3 })` and print results

This is the recommended pattern for containerized deployments — credentials are never baked into the image, they're injected at runtime via environment variables or secrets managers (AWS Secrets Manager, Kubernetes Secrets, etc.).
