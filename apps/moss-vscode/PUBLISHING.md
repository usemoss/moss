# Publishing Moss Code Search to the VS Code Marketplace

## Prerequisites

### 1. Publisher account (`moss-dev`)

1. Sign in at [Visual Studio Marketplace Publisher Management](https://marketplace.visualstudio.com/manage).
2. Create a publisher named **`moss-dev`** (must match `package.json` → `"publisher"`).
3. Complete publisher verification (Microsoft may require domain or identity verification).
4. Create a Personal Access Token on Azure DevOps with **Marketplace → Manage** scope.
5. Login locally: `npx @vscode/vsce login moss-dev`

> **Note:** Only a verified Moss team member can complete publisher registration. This repo includes packaging/CI; the publisher account itself must be created in the Marketplace portal.

### 2. Privacy policy

The Marketplace listing must link to [PRIVACY.md](./PRIVACY.md). Add the URL to the extension README and the marketplace listing description.

## Build a release VSIX

```bash
cd apps/moss-vscode
npm ci
npm run package
npm run verify-package
```

This will:

1. Compile `dist/extension.js` and `dist/mossWorker.js`
2. Install **all** `@moss-dev/moss-core-*` platform binaries into `node_modules`
3. Bundle production dependencies into `moss-vscode-0.1.0.vsix`

## Publish

```bash
npx @vscode/vsce publish -p <AZURE_DEVOPS_PAT>
```

Or upload the `.vsix` manually in the publisher portal.

## Open VSX (Cursor / VSCodium)

```bash
npx ovsx publish moss-vscode-0.1.0.vsix -p <OPEN_VSX_TOKEN>
```

## CI

GitHub Actions workflow `.github/workflows/moss-vscode-ci.yml` runs on every PR/push:

- Typecheck + build on macOS, Ubuntu, Windows
- Package VSIX on Ubuntu
- Verify native binaries are bundled

## Node runtime for the Moss worker

The extension runs Moss in a child Node process. Resolution order:

1. `moss.nodePath` setting (manual override)
2. `NODE_BINARY` environment variable
3. System Node (`node` on PATH)
4. VS Code embedded Node (`process.execPath` + `ELECTRON_RUN_AS_NODE`)

If indexing fails with a native crash, install Node 20.4+ and set `moss.nodePath`, or set `NODE_BINARY`.
