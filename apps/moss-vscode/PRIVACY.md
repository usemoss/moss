# Moss Code Search — Privacy Policy

Last updated: July 10, 2026

Moss Code Search is a VS Code extension published by Moss. This policy describes what data the extension processes and where it goes.

## Summary

- **Your source code is indexed locally on your machine** by default.
- **Optional cloud sync** uploads locally computed embeddings and chunk metadata to your Moss Cloud project when enabled.
- **Moss API credentials** are stored in VS Code Secret Storage on your device.
- The Moss SDK may emit **usage telemetry** unless disabled (see below).

## Data stored on your device

| Data | Location | Purpose |
|------|----------|---------|
| Moss Project ID / Key | VS Code Secret Storage | Authenticate with Moss Cloud |
| Search index (embeddings + chunks) | Extension global storage | Fast local semantic search |
| Index metadata (`meta.json`) | Extension global storage | Restore indexes between sessions |

Credentials are not written to your workspace or synced to git by the extension.

## Data sent to Moss Cloud

When you provide Moss credentials and use the extension:

1. **Authentication** — Project ID and key are sent to Moss to validate your session when opening a `SessionIndex`.
2. **Cloud sync** (when `moss.cloudSync` is enabled or you click **Sync to Cloud**) — Indexed document text, metadata (file paths, line numbers), and locally computed embeddings are uploaded via `pushIndex()` to the index named `vscode-{workspaceHash}` in your Moss project.
3. **Cloud restore** — When no local cache exists, the extension may download a previously pushed index from your Moss project.

Moss does **not** re-embed your documents server-side during `pushIndex`; embeddings are computed on your machine.

## Telemetry

The `@moss-dev/moss` SDK may send anonymized usage telemetry (for example device attribution during `session()` / `loadIndex()`). To opt out, set this environment variable before launching VS Code:

```bash
export MOSS_DISABLE_TELEMETRY=1
```

## Data we do not collect

The extension does not operate its own analytics server. We do not receive your search queries unless you explicitly use Moss Cloud APIs outside this extension's local search path.

## Third parties

- **Moss Cloud** ([moss.dev](https://moss.dev)) — hosts optional synced indexes and handles authentication for your project credentials.
- **VS Code / Cursor** — hosts the extension runtime and Secret Storage.

## Your choices

- Disable cloud upload: set `"moss.cloudSync": false` in VS Code settings.
- Remove local indexes: delete the extension's global storage or run **Moss: Rebuild Index** after clearing cache.
- Remove cloud indexes: delete the index from your Moss project dashboard (index name `vscode-{hash}`).

## Contact

For privacy questions, contact Moss via [moss.dev](https://moss.dev).
