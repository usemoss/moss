---
name: moss-search
description: Search Moss semantic indexes for relevant documents, code, docs, runbooks, and architecture context. Use when the user asks about their system, needs to debug errors, understand architecture, plan refactors, prepare for review, or search indexed knowledge. Triggers on "search", "find", "how does", "where is", "why", "error", "bug", "broken", "explain", "architecture", "refactor", "review", "caveats".
argument-hint: <query>
allowed-tools: mcp__moss-search__query, mcp__moss-search__list_indexes, mcp__moss-search__load_index
---

# Moss Search

Search your Moss semantic search indexes.

## Usage

1. Use `mcp__moss-search__query` with the user's question or a refined query.
2. If no index name is given, use `MOSS_INDEX_NAME` or call `mcp__moss-search__list_indexes` to discover indexes.
3. For repeated searches, call `mcp__moss-search__load_index` first for sub-10ms local queries.

## Query Strategy

- Start broad with the user's question as-is.
- If results are sparse or low-score (<0.3), try 1-2 narrower follow-up queries.
- Synthesize results into a clear answer — never dump raw chunks.

## Query Angles by Context

Adapt your queries to the user's intent:

- **Debugging**: Search the error message, system name + "error"/"fix", related components, prior incidents.
- **Architecture**: Search the topic directly, topic + "architecture"/"design", related modules.
- **Refactoring**: Search current implementation, similar patterns, prior migrations, dependencies.
- **Review prep**: Search invariants, similar codepaths, known caveats, related ADRs.
- **General**: Rephrase into 1-3 targeted queries, try synonyms and alternate phrasings.

## Auto-Search Context

If the UserPromptSubmit hook already injected Moss context, don't make redundant queries — use what's already there.
