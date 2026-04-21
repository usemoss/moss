# Moss + Liteparse Demo (LlamaIndex)

A full-stack demonstration of document processing and semantic search powered by **Liteparse** (PDF parsing) and **Moss** (vector search).

## Overview

This demo application showcases:
- **PDF Document Processing**: Parse and extract text from PDFs using Liteparse
- **Intelligent Chunking**: Split documents into semantic chunks with sentence-based overlap
- **Vector Search**: Create and query indexes using Moss for semantic retrieval
- **Real-time Streaming**: Get search results streamed via Server-Sent Events (SSE)
- **Modern UI**: Next.js frontend with TypeScript, React 19, and Tailwind CSS

## Architecture

```
┌─────────────────────┐
│  Next.js Frontend   │
│  (React + TS)       │
└──────────┬──────────┘
           │ HTTP/SSE
           ↓
┌─────────────────────┐
│   FastAPI Backend   │
│  - PDF Upload       │
│  - Text Chunking    │
│  - Moss Index       │
│  - Query/Stream     │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   Moss Service      │
│   (Vector Search)   │
└─────────────────────┘
```

## Project Structure

```
moss-llamaindex/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main FastAPI application
│   ├── seed_index.py       # Pre-index PDFs into Moss
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # Docker container setup
│   ├── .env.example        # Environment variables template
│   └── .dockerignore       # Docker ignore patterns
│
└── frontend/               # Next.js frontend
    ├── app/               # Next.js app directory
    │   ├── layout.tsx     # Root layout component
    │   └── globals.css    # Global styles
    ├── components/        # React components
    │   ├── common/        # Shared components (navbar, footer)
    │   ├── demo/          # Demo-specific components (chat, upload, progress)
    │   └── ui/            # UI primitives (buttons)
    ├── lib/              # Utilities
    ├── public/           # Static assets
    ├── package.json      # Node.js dependencies
    ├── tsconfig.json     # TypeScript config
    ├── tailwind.config.js # Tailwind CSS config
    └── next.config.mjs   # Next.js config
```

## Prerequisites

- **Python 3.12+** (backend)
- **Node.js 20+** (frontend & Liteparse)
- **Moss Project Credentials** (MOSS_PROJECT_ID and MOSS_PROJECT_KEY)
- Docker (optional, for containerized backend)

## Setup

### Backend Setup

1. **Install Python dependencies**:
   ```bash
   cd apps/moss-llamaindex/backend
   pip install -r requirements.txt
   python -c "import nltk; nltk.download('punkt_tab')"
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   # MOSS_PROJECT_ID=your_project_id
   # MOSS_PROJECT_KEY=your_project_key
   # SEED_INDEX_NAME=transformer-paper (optional)
   ```

3. **Run the backend**:
   ```bash
   cd apps/moss-llamaindex/backend
   python main.py
   # Server runs on http://localhost:8000
   ```

### Frontend Setup

1. **Install Node.js dependencies**:
   ```bash
   cd apps/moss-llamaindex/frontend
   npm install
   ```

2. **Run the development server**:
   ```bash
   npm run dev
   # Server runs on http://localhost:3001
   ```

3. **Build for production**:
   ```bash
   npm run build
   npm start
   ```

### Docker Setup (Backend Only)

1. **Build the Docker image**:
   ```bash
   cd apps/moss-llamaindex/backend
   docker build -t moss-llamaindex .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8000:8000 \
     -e MOSS_PROJECT_ID=your_project_id \
     -e MOSS_PROJECT_KEY=your_project_key \
     -e SEED_INDEX_NAME=transformer-paper \
     moss-llamaindex
   ```

## Environment Variables

### Backend (.env or docker -e)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `MOSS_PROJECT_ID` | Yes | Moss project identifier | `proj_abc123` |
| `MOSS_PROJECT_KEY` | Yes | Moss API key for authentication | `sk_live_...` |
| `SEED_INDEX_NAME` | No | Pre-indexed seed document name | `transformer-paper` |
| `SEED_CHUNK_COUNT` | No | Number of chunks in seed index | `512` |
| `PORT` | No | Server port (Docker only) | `8000` |

## API Endpoints

### Backend Routes

All endpoints are prefixed with `/llamaindex`.

#### Health Check
- **GET** `/health`
  - Returns: `{ "status": "ok" }`
  - Use for liveness/readiness checks

#### Upload & Index PDFs
- **POST** `/api/upload`
  - Request: Form data with PDF files (max 5 files)
  - Response:
    ```json
    {
      "session_id": "a1b2c3d4",
      "chunk_count": 512,
      "elapsed_seconds": 45,
      "files": ["document.pdf"]
    }
    ```
  - Creates a new Moss index and returns session ID

#### Query with Streaming
- **POST** `/api/chat/{session_id}`
  - Request: `{ "question": "What is this about?" }`
  - Response: Server-Sent Events (SSE)
  - Event format:
    ```json
    {
      "type": "shard",
      "shard": 1,
      "total": 1,
      "time_ms": 234,
      "index": "pdf-a1b2c3d4",
      "docs": [
        {
          "id": "document.pdf-p1-c0",
          "text": "Chunk content...",
          "score": 0.892,
          "source": "document.pdf",
          "page": "1"
        }
      ]
    }
    ```

#### Load Sample Index
- **GET** `/api/sample`
  - Returns: Pre-indexed seed document session details
  - Only available if `SEED_INDEX_NAME` is configured

#### Stream Status (Placeholder)
- **GET** `/api/stream/{session_id}`
  - Returns: SSE with completion status

## Key Components

### Backend

**main.py** - FastAPI Application
- PDF upload and parsing with Liteparse
- Intelligent text chunking with sentence-based overlap
- Moss index creation and querying
- SSE-based result streaming
- Session management for multiple concurrent uploads

**seed_index.py** - Index Pre-creation Tool
- Pre-index a PDF into Moss for caching
- Useful for creating demo indexes that load instantly
- Usage: `python seed_index.py /path/to/file.pdf index-name`

### Frontend

**chat-section.tsx** - Chat Interface
- Query interface with message display
- Integrates with backend SSE for real-time results
- Shows source documents and relevance scores

**upload-section.tsx** - File Upload
- Drag-and-drop PDF upload
- Multi-file support (up to 5 files)
- File validation

**indexing-progress.tsx** - Progress Tracking
- Shows indexing progress
- Displays chunk count and processing time
- Real-time status updates

## Workflow

1. **User uploads PDF(s)** via the frontend
2. **Backend processes**:
   - Parse PDFs with Liteparse
   - Extract text and split into chunks
   - Create Moss index with document metadata
3. **User queries** the indexed documents
4. **Backend streams** relevant chunks back with similarity scores
5. **Frontend displays** results with source attribution

## Text Chunking Strategy

Documents are split into semantic chunks with the following logic:

- **Target**: ~400 words per chunk
- **Overlap**: Last 2 sentences carried forward to next chunk
- **Method**: Sentence-based splitting (NLTK punkt tokenizer)
- **Result**: Complete sentences preserved in all chunks

This approach balances:
- Query context (enough content per chunk)
- Relevance (sentence boundaries preserve meaning)
- Efficiency (controlled overlap prevents data duplication)

## Development Tips

### Adding New Features
1. Frontend changes go in `/frontend/components/`
2. Backend API changes go in `/backend/main.py`
3. Update `.env.example` if new env vars are added

### Testing the API
```bash
# Health check
curl http://localhost:8000/llamaindex/health

# Upload a PDF
curl -X POST \
  -F "files=@document.pdf" \
  http://localhost:8000/llamaindex/api/upload

# Query (replace SESSION_ID and use the returned session_id)
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?"}' \
  http://localhost:8000/llamaindex/api/chat/SESSION_ID
```

### Debugging
- Backend logs: Check console output from `python main.py`
- Frontend logs: Open browser DevTools (F12)
- Docker logs: `docker logs <container_id>`

## Performance Notes

- **PDF Parsing**: Depends on PDF size and complexity
- **Indexing**: Moss index creation time varies by document size
- **Queries**: Results return within seconds, streamed via SSE
- **Session Storage**: In-memory (lost on server restart)

## Limitations

- Session data is not persisted (lost on restart)
- Max 5 files per upload
- Requires active Moss project credentials
- PDF OCR is disabled (extract only from text layers)

## Troubleshooting

### "No sample index available"
- Set `SEED_INDEX_NAME` in `.env` and restart

### "Liteparse: command not found"
- Install Node.js 20+ and run: `npm install -g @llamaindex/liteparse`

### "MOSS_PROJECT_ID/KEY not set"
- Configure `.env` with your Moss credentials

### Frontend can't reach backend
- Ensure backend is running on `http://localhost:8000`
- Check CORS is enabled (it is by default)
- Verify backend health: `curl http://localhost:8000/llamaindex/health`

## License

Part of the Moss project. See root LICENSE for details.
