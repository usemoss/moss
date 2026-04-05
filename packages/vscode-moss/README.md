# vscode-moss

VS Code extension for **semantic codebase search** with [Moss](https://moss.dev). This package is under active development.

**Distribution:** install from a **`.vsix`** file only — this extension is **not** published on the VS Code Marketplace.

## Install from VSIX

1. Build the VSIX (or use one attached to a release):

   ```bash
   cd packages/vscode-moss
   npm ci
   npm run check && npm run compile
   npx vsce package
   ```

   This produces **`vscode-moss-0.0.1.vsix`** (or whatever version is in `package.json`) in the current directory. Size depends on **`@moss-dev/moss`** and its **`@moss-dev/moss-core`** (N-API) dependency shipped in `node_modules`.

2. In VS Code or Cursor: **Extensions** → **`…`** (Views and More Actions) → **Install from VSIX…** → choose the `.vsix` file.

3. Reload the window if prompted, then configure Moss (**Moss: Configure credentials** or settings / env) and use **Moss: Index Workspace** as usual.

## Search your workspace

1. Set credentials: **Moss: Configure credentials** (pick **Project ID and project key** or **Project key only**; in key-only mode, an empty field removes the stored key), or set **`moss.projectId`** / **`moss.projectKey`** in settings, or **`MOSS_PROJECT_ID`** / **`MOSS_PROJECT_KEY`** in the environment.
2. Run **Moss: Index Workspace** (crawl + chunk + upload to Moss).
3. Open the **Moss** icon in the activity bar → **Search**, or run **Moss: Search** from the Command Palette. Enter a query; click a result to jump to the file and line range.

To change Moss options without opening Search, run **Moss: Open Settings** from the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).

Indexing and search logs go to **View → Output** → channel **Moss**. Set **`moss.logVerbose`** to `true` for step-by-step indexing and search logs (default is a shorter summary).

The **status bar** shows **Moss: not indexed** or **Moss: indexed … ago** (when a folder is open). Click it to run **Moss: Index Workspace**.

### Privacy

File paths and file contents you index are sent to **Moss** (cloud) for embedding and storage in your project’s index. Queries are also processed by Moss. Do not index secrets or data you are not allowed to send to a third-party service. See [moss.dev](https://moss.dev) for product terms and security expectations.

### Settings (`moss.*`)

| Setting | Purpose |
|--------|---------|
| `projectId` / `projectKey` | Moss project credentials (key: prefer SecretStorage via commands). |
| `indexName` | Index name (default derived from workspace folder name). |
| `modelId` | Embedding model for `createIndex`. |
| `includeGlob` / `excludeGlob` | Which files to crawl when indexing. |
| `maxFileSizeBytes` | Skip larger files. |
| `topK` | Number of search hits. |
| `alpha` | Hybrid search blend: `1.0` = semantic only, `0.0` = keyword only (default `0.8`). |
| `queryMode` | `local` (download index) vs `cloud` (API-only queries). |
| `chunkMaxLines` / `chunkOverlapLines` | Line-based chunking when indexing. |
| `logVerbose` | Extra lines in **Output → Moss**. |

## Development

### Automated tests

From `packages/vscode-moss`:

```bash
npm ci
npm run check    # TypeScript
npm test         # Vitest (chunking, paths, config, moss client factories)
npm run compile
```

### Manual QA (before release)

Use the **Extension Development Host** (F5 from repo root or this package) with real Moss credentials.

1. **Happy path:** Open a small test folder → configure credentials → **Moss: Index Workspace** → **Moss: Search** for text you know exists → click a result → editor jumps to the right file and range.
2. **Cancel indexing:** Start **Moss: Index Workspace** on a larger tree → cancel from the notification → confirm no crash; **Output → Moss** notes cancellation.
3. **Multi-root:** Open a workspace with two folders → index → search → open a hit from each root (paths resolve via `workspaceFolderIndex`).

### Troubleshooting (`loadIndex` / local search)

**Moss: Index Workspace** and sidebar search use **`@moss-dev/moss`** (`createIndex`, `deleteIndex`, `loadIndex`, `query`) — one client for cloud mutations and local or cloud queries.

- If **`loadIndex`** or local **`query`** fails, read the error in **Output → Moss**. Common causes: Node / native addon constraints in the extension host, WASM path differences, or network/proxy blocking the index download.
- Search still runs **`query`** after a failed `loadIndex`; the SDK falls back to **cloud** query (same idea as setting **`moss.queryMode`** to **`cloud`**).
- If local mode is **unreliable** in your environment, use **`moss.queryMode`: `cloud`** in settings.

This extension uses **`"type": "module"`** (ESM); **`out/extension.js`** is built as ESM (`NodeNext`).

### Credentials (F5 / dev)

Either:

- Set **`MOSS_PROJECT_ID`** and **`MOSS_PROJECT_KEY`** in the environment (recommended for F5: edit `.vscode/launch.json` at the **repository root** under `env`, or use your OS environment), or  
- Set **`moss.projectId`** and **`moss.projectKey`** in VS Code Settings (workspace or user).

### Run the extension (monorepo)

1. Open the **`moss` repository root** in VS Code.
2. **Terminal:** `cd packages/vscode-moss && npm install && npm run compile` (or rely on the watch task).
3. **Run and Debug** → **vscode-moss: Run Extension** (uses `packages/vscode-moss` as `extensionDevelopmentPath`).
4. In the Extension Development Host, use **Moss: Configure credentials**, **Moss: Index Workspace**, and **Moss: Search** as needed.
5. Open **Output** → channel **Moss** for logs.

### Run the extension (this folder only)

Open **`packages/vscode-moss`** as the workspace folder and use **Run Extension (open this folder as workspace)**.

### Build

- **`npm run check`** — TypeScript (`tsc --noEmit`).
- **`npm run compile`** — bundles `src/extension.ts` → `out/extension.js` with **esbuild** (Moss packages stay **external** and load from `node_modules`).
- **`npm run watch`** — esbuild watch (no typecheck loop; run **`check`** in another terminal or before commit).

```bash
npm install
npm run check && npm run compile
npm run watch   # optional during development
```

### Package VSIX (build only)

Same as [Install from VSIX](#install-from-vsix) step 1. You can also run **`npm run package`** (`vsce package`), which triggers **`vscode:prepublish`** (check + compile) first.

Bundling only shrinks **our** entry file; **`@moss-dev/moss`** and **`@moss-dev/moss-core`** remain **external** and ship inside the VSIX via `node_modules`.

`package.json` still includes **`icon`** and **`galleryBanner`** for consistency if you ever list the extension elsewhere; they are not required for VSIX install.
