---
name: moss
description: Use Moss semantic search for project memory — find relevant code, docs, architecture context, runbooks, and prior implementations. Triggers on questions about the user's system, debugging, refactoring, code archaeology, or when indexed knowledge would help answer a question. Also triggers when the user mentions Moss, searching their knowledge base, or querying indexed content.
---

# Moss Semantic Search

Moss is a sub-10ms semantic search runtime indexed over the user's codebase, docs, runbooks, and other project knowledge. Use it as persistent project memory.

## Auto-Search Context

The UserPromptSubmit hook automatically injects relevant Moss context for knowledge-seeking prompts (questions, debugging, architecture). If the hook already injected context that answers the question, do NOT make redundant MCP queries — use what you have.

## MCP Tools

Use these when you need deliberate retrieval beyond what auto-search provides:

- **`query`** — Search an index. Start broad, narrow with follow-up queries if results are weak. Synthesize results; don't dump raw chunks.
- **`load_index`** — Download an index into local memory for sub-10ms queries. Call this before repeated `query` calls on the same index. If `MOSS_INDEX_NAME` was configured, the default index is preloaded automatically.
- **`list_indexes`** — See available indexes.
- **`create_index`** — Create a new index with documents.
- **`add_docs`** — Add documents to an existing index.
- **`delete_docs`** / **`delete_index`** — Remove documents or indexes.
- **`get_index`** / **`get_docs`** — Inspect index metadata or retrieve documents.
- **`get_job_status`** — Check status of async Moss jobs.

## MCP Prompts (Slash Commands)

Reusable workflows surfaced as `/mcp__moss__*` commands:

- **`/mcp__moss__investigate_bug`** — Debug errors by searching for related runbooks, prior fixes, service docs.
- **`/mcp__moss__understand_system`** — Map architecture: key modules, docs, entrypoints for a topic.
- **`/mcp__moss__plan_refactor`** — Find related patterns, prior migrations, blast radius before refactoring.
- **`/mcp__moss__review_with_context`** — Retrieve invariants, similar codepaths, caveats before code review.

## Query Strategy

1. Start with the user's question as a direct query.
2. If results are sparse or low-score, try narrower follow-up queries with specific terms.
3. Combine results from multiple queries when needed.
4. Synthesize retrieved context into a clear answer — never dump raw search results.
5. If scores are all below 0.3, the indexed knowledge likely doesn't cover this topic.

## Index Lifecycle

- If `MOSS_INDEX_NAME` is set, the default index is preloaded on startup. Queries start on cloud (~100-500ms) and become local (~5ms) after preload completes.
- For non-default indexes, call `load_index` before running repeated queries.
- `query` always works even without `load_index` — it falls back to cloud search.
