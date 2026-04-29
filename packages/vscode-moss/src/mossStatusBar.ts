import * as vscode from "vscode";
import {
  MOSS_LAST_INDEXED_KEY,
  type LastIndexedState,
} from "./lastIndexed.js";

const TICK_MS = 60_000;

let refreshStatus: (() => void) | undefined;

function formatIndexedAgo(timestamp: number): string {
  const sec = Math.floor((Date.now() - timestamp) / 1000);
  if (sec < 10) return "just now";
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 48) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

/**
 * Registers the status bar item (click → **Moss: Index Workspace**) and periodic refresh.
 */
export function registerMossStatusBar(context: vscode.ExtensionContext): void {
  const item = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  item.command = "moss.indexWorkspace";

  const update = (): void => {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders?.length) {
      item.text = "$(search) Moss";
      item.tooltip =
        "Moss semantic search — open a folder, then click to run Moss: Index Workspace.";
      item.show();
      return;
    }

    const state = context.workspaceState.get<LastIndexedState>(
      MOSS_LAST_INDEXED_KEY
    );
    if (!state?.timestamp) {
      item.text = "$(search) Moss: not indexed";
      item.tooltip =
        "No Moss index for this workspace yet.\nClick to run Moss: Index Workspace.";
      item.show();
      return;
    }

    item.text = `$(search) Moss: indexed ${formatIndexedAgo(state.timestamp)}`;
    item.tooltip = [
      `Last index: “${state.indexName}”`,
      `${state.docCount} chunks · ${state.fileCount} files`,
      "Click to run Moss: Index Workspace.",
    ].join("\n");
    item.show();
  };

  refreshStatus = update;
  update();

  const interval = setInterval(update, TICK_MS);
  context.subscriptions.push(
    { dispose: () => clearInterval(interval) },
    item,
    vscode.workspace.onDidChangeWorkspaceFolders(() => update())
  );
}

/** Call after a successful index so “Xm ago” updates immediately. */
export function notifyMossIndexed(): void {
  refreshStatus?.();
}
