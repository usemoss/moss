# Gemma Moss Integration

Moss delivers sub-10ms semantic retrieval for your Gemma-powered chatbot running locally via Ollama. Gemma decides when to search using native tool calling — no custom protocols, no overhead on casual turns.

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- [Ollama](https://ollama.com/) installed
- [Docker](https://docs.docker.com/get-docker/) (for Open WebUI)

## Installation

```bash
pip install gemma-moss
```

## Setup

### 1. Install and start Ollama

```bash
brew install ollama
brew services start ollama
```

### 2. Pull Gemma 4

```bash
ollama pull gemma4
```

### 3. Keep the model hot

By default Ollama unloads models after 5 minutes of inactivity, causing cold start delays. Set a longer keep-alive:

```bash
curl http://localhost:11434/api/generate -d '{"model":"gemma4","keep_alive":"24h","prompt":""}'
```

### 4. Reduce context length (optional)

Gemma 4 defaults to 32K context. If your conversations are short, reducing to 8192 frees GPU memory and speeds up inference. Set this in Open WebUI's model settings or via the Ollama API.

---

## Open WebUI Setup (Recommended)

The best way to use Gemma + Moss is through Open WebUI with the Moss tool plugin.

### 1. Build the Docker image

The standard Open WebUI image doesn't include the Moss SDK. Use our custom Dockerfile that adds GLIBC 2.38+ support and the Moss package:

```bash
cd packages/gemma-moss/openwebui-tool
docker build -t open-webui-moss .
```

### 2. Start Open WebUI

```bash
docker run -d -p 8080:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  open-webui-moss
```

Open **http://localhost:8080** and create an account.

### 3. Add the Moss tool

1. Go to **Workspace > Tools > + (Create)**
2. Paste the contents of `openwebui-tool/moss_search.py`
3. Save

### 4. Configure credentials

Click the **gear icon** on the Moss tool and set:

| Setting | Value |
|---------|-------|
| `moss_project_id` | Your Moss project ID |
| `moss_project_key` | Your Moss project key |
| `moss_index_name` | Your Moss index name |
| `top_k` | Number of results (default: 5) |
| `alpha` | Semantic vs keyword blend (default: 0.8) |

### 5. Chat

1. Start a new chat
2. Select **gemma4** as the model
3. Enable the **Moss Knowledge Base Search** tool (click the + near the input)
4. Ask questions — Gemma will call Moss when it needs information

The tool shows live status: "Loading index...", "Searching...", and result count with timing.

---

## CLI Usage

For a terminal-based chatbot without Open WebUI:

### 1. Set up environment

```bash
cd packages/gemma-moss
cat > .env << EOF
MOSS_PROJECT_ID=your-project-id
MOSS_PROJECT_KEY=your-project-key
MOSS_INDEX_NAME=your-index-name
OLLAMA_MODEL=gemma4
EOF
```

### 2. Create a Moss index (one-time)

```bash
uv run python examples/moss-create-index-demo.py
```

### 3. Start the chatbot

```bash
uv run python examples/moss-gemma-demo.py
```

Commands: `/reset` (clear history), `/quit` (exit)

---

## Python SDK

### MossRetriever

Reusable retrieval adapter. Can be used independently of the session.

```python
from gemma_moss import MossRetriever

retriever = MossRetriever(
    project_id="...",
    project_key="...",
    index_name="my-index",
)
await retriever.load_index()

# Raw search
result = await retriever.query("search terms")

# Formatted for LLM context
context = await retriever.retrieve("search terms")
```

### GemmaMossSession

Chat session with native tool calling. Gemma decides when to search Moss.

```python
from gemma_moss import GemmaMossSession, MossRetriever

retriever = MossRetriever(index_name="my-index")
await retriever.load_index()

session = GemmaMossSession(
    retriever=retriever,
    model="gemma4",
    index_description="a customer FAQ covering orders, shipping, and returns",
)

response = await session.ask("How do refunds work?")
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `retriever` | (required) | A `MossRetriever` instance |
| `model` | `gemma4` | Ollama model name |
| `ollama_host` | `None` | Ollama server URL |
| `system_prompt` | `None` | Override default system prompt |
| `index_description` | `"a knowledge base"` | Describes what's searchable |
| `history` | `None` | Initial conversation history |

| Method | Description |
|--------|-------------|
| `ask(message)` | Send a message, return response |
| `ask_stream(message)` | Send a message, yield response |
| `reset()` | Clear conversation history |
| `get_history()` | Return a copy of conversation history |

---

## Architecture

Gemma gets Moss registered as an Ollama tool (`search_knowledge_base`). Per turn:

1. User sends a message
2. Gemma either responds directly (1 Ollama call) or calls the tool (2 Ollama calls)
3. If Gemma calls the tool, Moss runs a sub-10ms in-memory search and returns results
4. Gemma answers using the retrieved context

```
User message
    |
    v
Gemma (via Ollama, with Moss tool)
    |
    +-- Direct answer (no search needed)
    |
    +-- Tool call: search_knowledge_base(query)
            |
            v
        Moss in-memory search (~1-10ms)
            |
            v
        Gemma answers with context
```

---

## Performance Tips

| Optimization | Impact | How |
|-------------|--------|-----|
| Model keep-alive | No cold starts between messages | `keep_alive: 24h` via API |
| Smaller context | Faster per-token generation | Set context to 8192 in model settings |
| Moss in-memory | Sub-10ms search (~65x faster than cloud) | `load_index()` (automatic in the tool) |
| Auto-refresh | Index stays synced without restarts | Enabled in the tool |

> **Note on Flash Attention:** Ollama supports `OLLAMA_FLASH_ATTENTION=1` and `OLLAMA_KV_CACHE_TYPE=q8_0`, but these can actually slow down inference on Apple Silicon (~56 tok/s vs ~65 tok/s default). Benchmark on your hardware before enabling. They may help on NVIDIA GPUs with CUDA.

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.usemoss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [Ollama Docs](https://ollama.com/docs)
- [Open WebUI Docs](https://docs.openwebui.com)
