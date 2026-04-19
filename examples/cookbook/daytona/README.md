# Log Ingestion Q&A Agent — MOSS + Daytona

Ask natural-language questions about system logs from a live sandbox.

**How it works:**

1. Spins up an isolated [Daytona](https://daytona.io) sandbox
2. Runs a workload inside it that generates structured logs
3. Indexes every log line into [MOSS](https://moss.dev) for semantic search
4. Starts an agent that searches MOSS to answer your questions

```
You: What errors occurred in the auth service?

Agent: Several authentication errors were logged throughout the day:
  - Invalid password attempts for admin@example.com (repeated)
  - Rate limiting triggered: 200 req/min from 10.0.0.42
  - Session token xyz789 not found
  Recommend reviewing brute-force protection and rate-limit thresholds.
```

---

## Project structure

```
daytona/
├── log_agent.py     # entrypoint — sandbox setup, indexing, Q&A loop
├── log_ingest.py    # log parser + MOSS LogSearchRetriever + LangChain tool
├── mock_logs.py     # sample workload: 1 200 log entries across 6 services
├── pyproject.toml
├── .env.example     # copy to .env and fill in keys
└── .env             # your keys (git-ignored)
```

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

> Don't have `uv`? Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`

### 2. Set environment variables

```bash
cp .env.example .env
# then open .env and fill in your keys
```

| Variable | Where to get it |
|---|---|
| `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) → project settings |
| `DAYTONA_API_KEY` | [app.daytona.io](https://app.daytona.io) → API keys |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |

---

## Usage

**Interactive REPL**

```bash
uv run python log_agent.py
```

```
Creating Daytona sandbox...
Sandbox ready  (id: b01c3d5a-...)

Generating logs in sandbox...
Indexing 1200 log entries (index: logs_b01c3d5a)...
Index ready  (job_id: ...)

Log Q&A ready. Type 'quit' to exit.

You: Were there any database connection issues?
Agent: Yes — the db-proxy service logged several critical events: connection
pool exhaustion (50/50 active connections), query timeouts after 30s on the
orders table, and a deadlock between transactions T1 and T2. Recommend
investigating connection pool sizing and adding query timeout alerts.

You: quit
```

**Single question (non-interactive)**

```bash
uv run python log_agent.py -q "Is there evidence of memory pressure?"
```

---

## How MOSS is used

Each log line is stored as a `DocumentInfo` with its full raw text as the
searchable content. Rather than brittle regex parsing, MOSS's hybrid
(semantic + keyword) search finds relevant entries regardless of log format.

```python
# log_ingest.py — one line becomes one document
DocumentInfo(
    id="app::a3f8c2d1b9e4",
    text="2025-04-15T14:32:01 WARN worker: Memory usage: 89% (7.1 GB / 8 GB)",
    metadata={"source": "app", "level": "WARN"},
)
```

The agent queries MOSS via the `log_search` tool, then the LLM synthesises
the retrieved entries into a human-readable answer.

---

## Replacing mock logs with real ones

`mock_logs.py` runs inside the Daytona sandbox and prints simulated log
entries to stdout. To use real logs instead, replace `_generate_logs` in
[log_agent.py](log_agent.py) with your own collection logic — for example,
reading from a running service, tailing a log file, or streaming from a
log aggregator.

```python
def _generate_logs(sandbox) -> List[str]:
    # Example: tail the last 2000 lines of a real app log
    response = sandbox.process.code_run(
        "import subprocess\n"
        "r = subprocess.run('tail -n 2000 /var/log/myapp/app.log', "
        "shell=True, capture_output=True, text=True)\n"
        "print(r.stdout)"
    )
    return [ln for ln in (response.result or "").splitlines() if ln.strip()]
```
