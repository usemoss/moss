# Self-Healing Code Agent - Moss + E2B

Use [Moss](https://moss.dev) semantic search to find relevant code, then validate a candidate fix inside an isolated [E2B](https://e2b.dev) cloud sandbox.

The flow is intentionally small:

1. Index a local codebase into Moss.
2. Search Moss with a bug report.
3. Ask a Groq-hosted LLM for a source-only patch.
4. Copy the project into E2B, run tests, apply the patch, and rerun tests.
5. Print the validated diff and clean up the sandbox.

## Project Structure

```text
e2b/
|-- code_agent.py          # entrypoint - Moss retrieval, Groq patching, E2B validation
|-- code_index.py          # source scanner + Moss document builder
|-- sandbox_runner.py      # E2B file/command helpers + patch parser
|-- sample_project/        # tiny broken Python project for the demo
|-- test_integration.py    # mocked helper tests, no credentials required
|-- pyproject.toml
|-- .env.example           # copy to .env and fill in keys
`-- .env                   # your keys, git-ignored
```

## Setup

### 1. Install dependencies

```bash
cd examples/cookbook/e2b
uv sync
```

For local tests and lint checks, include the dev extra:

```bash
uv sync --extra dev
```

### 2. Set environment variables

```bash
cp .env.example .env
# then open .env and fill in your keys
```

Fill in the keys:

| Variable | Where to get it |
|---|---|
| `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` | [moss.dev](https://moss.dev) project settings |
| `E2B_API_KEY` | [e2b.dev/dashboard](https://e2b.dev/dashboard) API keys |
| `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
| `GROQ_MODEL` | Optional, defaults to `llama-3.3-70b-versatile` |

## Usage

Run the sample agent:

```bash
uv run python code_agent.py
```

The bundled sample project has a tax calculation bug. The agent retrieves the relevant code and tests with Moss, asks Groq for a patch, then validates the patch in E2B:

```text
Indexing 4 source files in Moss (index: e2b-code-agent-a1b2c3d4)...
Moss retrieved:
  - src/ledger/totals.py
  - tests/test_totals.py

Creating E2B sandbox...
Baseline tests: failed (exit 1)
Patched tests: passed

Validated patch diff:
  diff --git a/src/ledger/totals.py b/src/ledger/totals.py
  ...
```

Run it against your own project:

```bash
uv run python code_agent.py \
  --project-root /path/to/repo \
  --issue "Users with annual plans are charged monthly tax twice" \
  --setup-command "python -m pip install -e . pytest" \
  --test-command "python -m pytest -q"
```

By default the demo creates a temporary Moss index and deletes it at the end so repeated runs do not consume your index quota. To keep one reusable index:

```bash
uv run python code_agent.py --index-name moss-e2b-code-agent --reuse-index
```

The first run creates the index. Later runs load it. Recreate the index when your project changes substantially so Moss does not retrieve stale code.

Keep the E2B sandbox for inspection:

```bash
uv run python code_agent.py --keep-sandbox
```

## How Moss Is Used

`code_index.py` turns source files into Moss `DocumentInfo` records with path, language, and Python symbol metadata. The document text includes the file path and source content, so a natural-language bug report can retrieve both implementation and tests.

```python
DocumentInfo(
    id="src/ledger/totals.py::a1b2c3d4e5f6",
    text="Path: src/ledger/totals.py\n\n```text\n...\n```",
    metadata={"path": "src/ledger/totals.py", "language": "python", "symbols": "format_total"},
)
```

The agent calls `client.query(..., QueryOptions(top_k=6, alpha=0.75))`, formats the hits, and passes only that focused context to the LLM.

## How E2B Is Used

`sandbox_runner.py` uses E2B's Python SDK to create a disposable sandbox, write project files, and run shell commands:

```python
from e2b import AsyncSandbox

sandbox = await AsyncSandbox.create(timeout=600)
await sandbox.files.write("/home/user/app/src/ledger/totals.py", source)
result = await sandbox.commands.run("python -m pytest -q", cwd="/home/user/app")
await sandbox.kill()
```

Commands are wrapped so non-zero test exits become structured results instead of aborting the flow. Patch paths are validated before writing, and the agent refuses patches that target `tests/` or `test_*.py` files.

## Run The Mocked Tests

These tests cover the source scanner, patch parser, safe sandbox paths, and command-result normalization without Moss, Groq, or E2B credentials:

```bash
uv run python test_integration.py
```

With the dev extra installed:

```bash
uv run python -m pytest -q
uv run python -m ruff check .
```

## Adapting The Pattern

- For AI code review, index the target branch, ask Moss for code related to the diff, then run the candidate change in E2B before posting review notes.
- For self-healing agents, keep the patch format as complete file replacements or switch to unified diffs if your agent already has a trusted patch applier.
- For larger repos, chunk files by function or class before creating Moss documents, and include test files in the index so retrieval can find validation targets too.
