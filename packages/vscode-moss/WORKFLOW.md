# vscode-moss indexing workflow

This document describes how **vscode-moss** turns workspace files into a Moss index. For a deeper, Markdown-documentation–oriented pipeline (render → HTML → chunking with heading context), see the Moss repo’s [**moss-md-indexer** workflow](https://github.com/usemoss/moss/blob/main/packages/moss-md-indexer/INDEXER-WORKFLOW.md).

## 1. High-level flow

1. **Configure** — Resolve Moss `projectId` / `projectKey` (settings, SecretStorage, or env). **`moss.*` for indexing/search is resolved against the first workspace folder** (`workspaceFolders[0]`); multi-root workspaces still index all roots, but include/exclude, `indexName`, chunk options, and search `topK` / `alpha` come from that folder’s effective settings only (see README).
2. **Discover** — Scan the workspace with `vscode.workspace.findFiles`, merging the primary folder’s `moss.includeGlob`, `moss.excludeGlob`, and extra safe excludes (e.g. `.git`, `node_modules`). Caps apply (`MAX_FILE_SCAN`, `MAX_MOSS_DOCUMENTS`).
3. **Filter** — Skip binary-by-extension files, oversize files, and paths that fail UTF-8 decode.
4. **Chunk** — For each file, read text and call `chunkFileContent` (`chunking.ts`):
   - **Structure-aware** — For supported `languageId` values (Markdown, JS/TS, and other Tree-sitter grammars wired in `structureChunking.ts`), emit chunks aligned to structure when possible.
   - **Fallback** — Otherwise use overlapping **line windows** (`chunkFileContentLineWindowsOnly` → `chunkLineWindowSegment` in `chunkCore.ts`), with small-file and max-character rules.
5. **Metadata** — Each chunk is a Moss **`DocumentInfo`**: `id`, `text`, and string-keyed `metadata` (`path`, `startLine`, `endLine`, optional `workspaceFolderIndex` / `workspaceFolderName` for multi-root).
6. **Upload** — `deleteIndex` (ignored if missing) then `createIndex` on **`MossClient`** with the chosen `modelId`.
7. **Local warm-up** — After a short settle delay, call `loadIndex` on a fresh client so the downloaded index is ready for fast local `query` (or cloud fallback if load fails).

## 2. Sidebar search (related)

When the **Search** webview is created, the extension warms the same index with `loadIndex` using a **session-scoped** client and load state. If `loadIndex` fails, that index name is marked so **the session does not retry** `loadIndex` (queries use cloud fallback until the session resets). The session is cleared when the view is disposed, Moss **credentials** change, relevant **`moss.*`** settings change (index/search/indexing-related, not `logVerbose`), or a full re-index completes (`notifySearchIndexStale`).

## 3. Code map

| Stage | Primary files |
|--------|----------------|
| Entry / progress UI | `indexWorkspace.ts` |
| File discovery | `indexWorkspace.ts` (`findWorkspaceFiles`) |
| Chunking | `chunking.ts`, `chunkCore.ts`, `structureChunking.ts` |
| Moss API | `@moss-dev/moss` (`MossClient`) |
