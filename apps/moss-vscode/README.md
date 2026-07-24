<p align="center">
  <img src="media/moss_avatar_core.png" alt="Moss" width="96" />
</p>

# Moss Code Search (VS Code)

Semantic search over your open workspace, powered by [Moss](https://moss.dev) — local-first, sub-10ms retrieval via `SessionIndex`.

## Features

- **Manual indexing** — click **Create Index** in the sidebar the first time
- **Persisted indexes** — reopening the same folder restores the saved index (no full rebuild)
- **Moss Cloud sync** — indexes are pushed to your Moss project via `pushIndex`; another machine can restore from cloud when local cache is missing
- Sidebar with live (debounced) semantic search after indexing
- Click a result to jump to file + line
- Incremental re-index on save / create / delete / rename (also saved to disk)
- Credentials via the sidebar **gear icon**, `Moss: Configure Credentials`, Secret Storage, or `.env`

## Setup

```bash
cd apps/moss-vscode
cp .env.example .env   # fill in MOSS_PROJECT_ID / MOSS_PROJECT_KEY
npm install
npm run build
```

Open this monorepo in VS Code / Cursor, then **Run and Debug → Run Extension** (F5).

Or from the Command Palette after installing a `.vsix`:

1. `Moss: Configure Credentials`
2. Open a workspace and wait for indexing
3. Open the **Moss Search** activity bar icon and type a query

## Commands

| Command | Description |
|---------|-------------|
| `Moss: Focus Search` | Focus the semantic search sidebar |
| `Moss: Create Index` | Index the open workspace (required before search) |
| `Moss: Rebuild Index` | Re-scan and re-index the workspace |
| `Moss: Sync Index to Cloud` | Upload the current index to Moss Cloud |
| `Moss: Configure Credentials` | Store project ID / key in Secret Storage |
| `Moss: Show Logs` | Open the Moss Code Search output channel |

## Settings

- `moss.projectId` / `moss.projectKey` — optional overrides
- `moss.includeGlobs` / `moss.excludeGlobs` — what to index (defaults skip `node_modules`, `dist`, `vendor`, `.venv`, build caches, etc.)
- `moss.topK` — result count (default 20)
- `moss.alpha` — hybrid blend (default 0.7; 1.0 = semantic)
- `moss.cloudSync` — push to Moss Cloud and restore from cloud when local cache is absent (default `true`)

## Cloud sync

Each workspace gets a stable Moss index name: `vscode-{workspaceHash}`. After **Create Index** (and on incremental saves), the extension:

1. Saves locally with Moss `saveToDisk` (fast reopen on the same machine)
2. Pushes to Moss Cloud with `pushIndex` (uploads locally-computed embeddings)

On a new machine with the same Moss credentials, opening the workspace will download the cloud index when no local cache exists. Use **Sync to Cloud** in the sidebar (or `Moss: Sync Index to Cloud`) to upload manually. Disable with `"moss.cloudSync": false` for fully offline-only behavior (local disk cache still works).

## Architecture

Extension host owns UI and file scanning. Moss native runtime runs in a separate Node worker (`dist/mossWorker.js`) so a native crash cannot take down VS Code. Sessions are named `vscode-{workspaceHash}`. Files are chunked into `DocumentInfo` records (`{path}#chunk-{n}`) with metadata for navigation.

After **Create Index**, the session is written with Moss `saveToDisk` under the extension global storage (`indexes/{workspaceHash}/`), plus a `meta.json` map of file → chunk counts. Reopening that folder loads the cache with `loadFromDisk` so search works immediately. Use **Moss: Rebuild Index** to force a full reindex.

Native modules (`@moss-dev/moss`, `@moss-dev/moss-core`) are bundled into the `.vsix` with all platform binaries. See [PUBLISHING.md](./PUBLISHING.md) to build and publish.

## Privacy

See [PRIVACY.md](./PRIVACY.md) for what data stays local, what syncs to Moss Cloud, and how to opt out of SDK telemetry (`MOSS_DISABLE_TELEMETRY=1`).
