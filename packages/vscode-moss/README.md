# vscode-moss

VS Code extension for **semantic codebase search** with [Moss](https://moss.dev). This package is under active development.

## Phase 1 — connectivity spike

The command **Moss: Run Phase 1 connectivity spike** validates, from the extension host:

1. `@inferedge-rest/moss` — `deleteIndex` (tolerate missing) + `createIndex` with three tiny documents on index `vscode-moss-phase1-spike`.
2. `@inferedge/moss` — `loadIndex` + `query` (local path).
3. If `loadIndex` / local `query` fails, a **cloud `query` fallback** runs so you still see end-to-end behavior. Check **Output → Moss Spike** for details.

### Credentials

Either:

- Set **`MOSS_PROJECT_ID`** and **`MOSS_PROJECT_KEY`** in the environment (recommended for F5: edit `.vscode/launch.json` at the **repository root** under `env`, or use your OS environment), or  
- Set **`moss.projectId`** and **`moss.projectKey`** in VS Code Settings (workspace or user).

### Run the extension (monorepo)

1. Open the **`moss` repository root** in VS Code.
2. **Terminal:** `cd packages/vscode-moss && npm install && npm run compile` (or rely on the watch task).
3. **Run and Debug** → **vscode-moss: Run Extension** (uses `packages/vscode-moss` as `extensionDevelopmentPath`).
4. In the Extension Development Host, **Command Palette** → **Moss: Run Phase 1 connectivity spike**.
5. Open **Output** panel → channel **Moss Spike** for the log.

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

### Package VSIX

```bash
npm run check && npm run compile
npx vsce package
```

The VSIX is still **large** (~100MB+) because **`@inferedge/moss`** pulls **`@huggingface/transformers`** and related assets for local embeddings. Bundling only shrinks **our** entry file; trimming install size further would need a different query architecture or upstream packaging changes.

**Marketplace:** `package.json` includes **`icon`** (`media/icon.png`, from the repo Moss logo) and **`galleryBanner`** for the listing.

See [PHASE1_SPIKE.md](./PHASE1_SPIKE.md) for `loadIndex` troubleshooting and default **`moss.queryMode`** guidance.
