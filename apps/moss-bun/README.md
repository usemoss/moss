# Moss Bun Application

Production-ready semantic search application built with **Moss** and **Bun**.

## What's Included

- **REST API Server** - Full-featured HTTP API for Moss operations
- **CLI Tool** - Command-line interface for searching and managing indexes
- **Test Suite** - Unit tests using Bun's built-in test runner
- **Docker Support** - Production-ready Docker image
- **High Performance** - 2-3x faster than Node.js with native TypeScript

## Quick Start

### 1. Install Dependencies

```bash
cd apps/moss-bun
bun install
```

### 2. Configure Credentials

```bash
cp .env.example .env
# Edit .env with your Moss credentials from https://moss.dev
```

### 3. Seed Sample Data

```bash
bun run seed
```

### 4. Start the Server

```bash
bun run dev        # Development with auto-reload
bun start          # Production mode
```

The server runs on `http://localhost:3000`

## Usage

### REST API

#### Health Check
```bash
curl http://localhost:3000/health
```

#### Initialize Index
```bash
curl -X POST http://localhost:3000/api/initialize \
  -H "Content-Type: application/json" \
  -d '{
    "indexName": "moss-demo",
    "documents": [
      {"id": "1", "text": "First document"},
      {"id": "2", "text": "Second document"}
    ]
  }'
```

#### Search
```bash
curl -X POST http://localhost:3000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is moss?",
    "topK": 5,
    "indexName": "moss-demo"
  }'
```

#### Batch Search
```bash
curl -X POST http://localhost:3000/api/search-batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["moss", "semantic search", "AI"],
    "topK": 3,
    "indexName": "my-docs"
  }'
```

### CLI

#### Search
```bash
# Search with default parameters
bun run cli search "what is moss?"

# Specify index and top results
bun run cli search "query" my-index 10
```

#### Initialize Index
```bash
bun run cli init my-index 10
```

#### Interactive Search
```bash
bun run cli interactive my-index
```

#### List Indexes
```bash
bun run cli list
```

#### Get Index Info
```bash
bun run cli info my-index
```

#### Delete Index
```bash
bun run cli delete my-index
```

## API Endpoints

### Health & Status
- `GET /health` - Server health check
- `GET /status` - Detailed server status

### Index Management
- `POST /api/initialize` - Create and load index
- `POST /api/load/:indexName` - Load existing index
- `GET /api/indexes` - List loaded indexes
- `GET /api/index/:indexName` - Get index metadata
- `DELETE /api/index/:indexName` - Delete index

### Search
- `POST /api/search` - Single semantic search
- `POST /api/search-batch` - Multiple queries at once

### Documents
- `POST /api/docs/add` - Add/update documents
- `DELETE /api/docs/delete` - Delete documents
- `GET /api/docs/:indexName/:docId` - Get document by ID

## Project Structure

```
moss-bun/
├── src/
│   ├── index.ts           # Main server
│   ├── cli.ts             # Command-line tool
│   ├── seed.ts            # Sample data seeder
│   └── moss.test.ts       # Tests
├── package.json           # Dependencies
├── bunfig.toml           # Bun configuration
├── Dockerfile            # Docker image
├── .env.example          # Environment template
└── README.md            # This file
```

## Configuration

Edit `.env` to customize:

```env
# Moss credentials (required)
MOSS_PROJECT_ID=your_id
MOSS_PROJECT_KEY=your_key

# Server port (default: 3000)
PORT=3000

# Default index for queries (default: "default")
DEFAULT_INDEX=my-index

# Environment
NODE_ENV=development
```

## Testing

```bash
# Run tests once
bun test

# Watch mode
bun run test:watch
```

Tests check:
- Index creation and loading
- Semantic search functionality
- Document operations
- Performance benchmarks
- Bun runtime features

## Docker Deployment

### Build Image
```bash
docker build -t moss-bun-app .
```

### Run Container
```bash
docker run -p 3000:3000 \
  -e MOSS_PROJECT_ID=your_id \
  -e MOSS_PROJECT_KEY=your_key \
  moss-bun-app
```

### With Docker Compose
```yaml
version: '3.8'
services:
  moss-bun:
    build: .
    ports:
      - "3000:3000"
    environment:
      MOSS_PROJECT_ID: ${MOSS_PROJECT_ID}
      MOSS_PROJECT_KEY: ${MOSS_PROJECT_KEY}
      DEFAULT_INDEX: my-index
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

## Performance

Bun provides significant advantages for this workload:

| Metric | Bun | Node.js |
|--------|-----|---------|
| Startup time | ~200ms | ~500-800ms |
| TypeScript overhead | None | ~100-200ms |
| Search queries | Same | Same |
| Package install | 3-4x faster | Baseline |

## Development

### Watch Mode
```bash
bun run dev
```

Auto-reloads on file changes.

### Building for Production
```bash
bun build src/index.ts --outdir dist --target bun
```

### Debugging
```bash
bun inspect src/index.ts
# Opens WebKit Inspector at chrome://inspect
```

## Examples

### Create Index from File
```bash
bun run cli init my-index 50
```

### Search and Display Results
```bash
bun run cli search "machine learning" my-index 5
```

### Batch Index Creation via API
```javascript
const documents = [
  { id: "1", text: "Document 1" },
  { id: "2", text: "Document 2" },
  // ... more documents
];

const response = await fetch("http://localhost:3000/api/initialize", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ indexName: "my-index", documents })
});

const result = await response.json();
console.log(result);
```

### Search from Node.js/Bun
```typescript
const results = await fetch("http://localhost:3000/api/search", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "what is moss?",
    topK: 5,
    indexName: "my-index"
  })
});

const data = await results.json();
console.log(data);
```

## Troubleshooting

### "MOSS_PROJECT_ID/KEY not set"
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### Port already in use
```bash
# Use a different port
PORT=3001 bun run start
```

### Build fails
```bash
# Clear cache and reinstall
rm -rf node_modules bun.lock
bun install
```

### Tests fail
Ensure you have valid Moss credentials in `.env` before running tests. Missing or invalid credentials may cause the tests to fail.

## Performance Tips

1. **Use Batch Search** for multiple queries at once
2. **Load indexes** once and reuse the connection
3. **Monitor memory** with `GET /status`
4. **Use topK=5** by default, increase only if needed
5. **Cache results** in your application layer

## Resources

- [Moss Documentation](https://docs.moss.dev)
- [Bun Documentation](https://bun.sh/docs)

## License

BSD 2-Clause License (see root LICENSE)
