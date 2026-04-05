import * as vscode from "vscode";
import { getMossConfig, resolveCredentials } from "./config.js";
import { mossLog } from "./mossLog.js";
import { ensureLocalIndexLoaded, getOrCreateSdkClient } from "./mossQueryState.js";

/**
 * Best-effort `loadIndex` for local query mode so the first search is often faster.
 * Uses the same SDK cache as search; overlapping preload + search may run `loadIndex` twice briefly.
 */
export async function preloadLocalMossIndex(
  context: vscode.ExtensionContext,
  log: vscode.OutputChannel,
  token: vscode.CancellationToken
): Promise<void> {
  if (token.isCancellationRequested) return;

  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) return;

  const creds = await resolveCredentials(context);
  if (!creds) return;

  const primary = folders[0]!;
  const cfg = await getMossConfig(context.secrets, primary);
  if (cfg.queryMode !== "local") return;

  if (token.isCancellationRequested) return;

  try {
    const sdk = getOrCreateSdkClient(creds.projectId, creds.projectKey);
    await ensureLocalIndexLoaded(sdk, cfg.indexName);
    mossLog(log, "Moss: Background index preload finished.", "verbose");
  } catch (e: unknown) {
    if (token.isCancellationRequested) return;
    const msg = e instanceof Error ? e.message : String(e);
    mossLog(
      log,
      `Moss: Background index preload failed (search will retry): ${msg}`,
      "verbose"
    );
  }
}
