---
name: moss-index
description: Index the current project into Moss using hash-based incremental sync. Use when the user wants to index their codebase, sync files to Moss, or set up search over their project. Triggers on "index", "sync to moss", "index my code", "add to moss", "index project".
argument-hint: [index-name]
allowed-tools: mcp__moss-search__sync_project, mcp__moss-search__load_index, mcp__moss-search__list_indexes
---

# Moss Index

Index the current project into Moss using incremental sync.

## Usage

Call `mcp__moss-search__sync_project` with:
- `dir`: current working directory (default ".")
- `indexName`: user-provided name, or `MOSS_INDEX_NAME`, or "codebase"

## What It Does

1. Walks git-tracked files (or directory tree if not a git repo)
2. Hashes each file (SHA-256) and compares against stored manifest
3. Only processes changed/added/deleted files — skips unchanged
4. Chunks into ~60-line segments with file path + line metadata
5. Uploads via addDocs(upsert: true) in batches of 100

## After Indexing

Call `mcp__moss-search__load_index` to enable sub-10ms local queries on the new index.
