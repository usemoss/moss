# Claude Code + Cognee + Moss on Daytona — Shared Memory Demo

Three Claude Code agents explore a Git repository in sequence, sharing a persistent memory graph powered by [Cognee](https://github.com/topoteretes/cognee) and [Moss](https://moss.dev), all running inside isolated [Daytona](https://daytona.io) sandboxes.

**What happens:**

1. A shared Daytona volume is created as a snapshot bucket
2. Three agents run sequentially — `arch`, `api`, `tests` — each in its own sandbox
3. Each agent syncs in the previous snapshot, runs Claude Code with the Cognee plugin, then syncs its updated state back out
4. Vectors are stored and searched in Moss (cloud); SQLite/Kuzu graph DBs live on local sandbox block storage
5. After all agents finish, an inspector sandbox reads the shared graph and prints row counts

```
[arch]  Maps project structure, entry points, modules → stores findings in Cognee
[api]   Recalls arch findings → describes API layer → stores findings in Cognee
[tests] Recalls both → describes test strategy → stores findings in Cognee

=== Inspecting shared graph ===
datasets: 1
data: 47
pipeline_runs: 3
nodes: 312
edges: 189
```

---

## Why this architecture

**No separate Cognee sandbox:** Daytona's public preview proxy rejects sandbox-to-sandbox traffic (`Connection reset by peer`), even with `public=True`.

**No volume-mounted databases:** Daytona volumes use mountpoint-s3 (FUSE). SQLite, Kuzu, and LanceDB all require random writes and file locking — mountpoint-s3 explicitly doesn't support these (`disk I/O error` on `CREATE TABLE`).

**What works:** Each agent runs Cognee in-process against local block storage. After the agent finishes, the state directory is tar'd into the volume as a single object (whole-object S3 writes are exactly what mountpoint-s3 is built for). The next agent extracts it before starting.

---

## Prerequisites

```bash
pip install daytona
```

| Variable | Where to get it |
|---|---|
| `DAYTONA_API_KEY` | [app.daytona.io](https://app.daytona.io) → API keys |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API keys |
| `LLM_API_KEY` | Your LLM provider (default: OpenAI) |
| `MOSS_PROJECT_ID` | [moss.dev](https://moss.dev) → project settings |
| `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) → project settings |

Optional:

| Variable | Default | Description |
|---|---|---|
| `LLM_MODEL` | `openai/gpt-4o-mini` | Model for Cognee graph extraction |
| `LLM_PROVIDER` | `openai` | LLM provider for Cognee |
| `DAYTONA_API_URL` | `https://app.daytona.io/api` | Daytona API endpoint |
| `TARGET_REPO` | `https://github.com/topoteretes/cognee` | Repo to explore (overridable via `--repo`) |

---

## Usage

```bash
python main.py
```

By default the agents explore the [cognee](https://github.com/topoteretes/cognee) repo. To use a different repository:

```bash
python main.py --repo https://github.com/your-org/your-repo
```

To keep the shared volume after the run (useful for debugging):

```bash
python main.py --keep-volume
```

---

## How Moss is used

Each agent stores and retrieves memories via the [cognee-community-vector-adapter-moss](https://pypi.org/project/cognee-community-vector-adapter-moss/) package, which registers Moss as Cognee's vector database backend:

```python
# Registered automatically in every sandbox via sitecustomize.py
from cognee_community_vector_adapter_moss import register
from cognee import config
config.set_vector_db_config({
    "vector_db_provider": "moss",
    "vector_db_key": os.getenv("VECTOR_DB_KEY"),
    "vector_db_name": os.getenv("VECTOR_DB_NAME"),
    "vector_dataset_database_handler": "moss",
})
```

Vectors are stored in Moss and persist across agent sandboxes. The SQLite/Kuzu graph (edges, nodes, datasets) is snapshotted to the Daytona volume between agents.

---

## How the Cognee plugin is used

Each agent runs with the [cognee-memory Claude Code plugin](https://github.com/topoteretes/cognee-integrations/tree/main/integrations/claude-code) via `--plugin-dir`. Agents use two slash commands:

- `/cognee-memory:cognee-remember` — store findings in the shared graph
- `/cognee-memory:cognee-search` — recall what earlier agents stored

The plugin's `SessionStart` hook timeout is bumped to 90 seconds (from the default 15) to accommodate Cognee's cold-import time on first run.

---

## Project structure

```
moss-cognee-daytona/
└── main.py     # entrypoint — volume setup, sandbox orchestration, agent tasks, graph inspection
```

---

New to Moss? See the [Moss Portal Quickstart](PORTAL_QUICKSTART.md) to get from zero to your first query in under 5 minutes.
