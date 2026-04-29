import * as vscode from "vscode";
import type { MossMetadata } from "./types.js";

function parsePositiveInt(s: string | undefined, fallback: number): number {
  if (s === undefined || s === "") return fallback;
  const n = parseInt(s, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

/** 0-based folder index; missing or invalid → 0. */
function parseWorkspaceFolderIndex(s: string | undefined): number {
  if (s === undefined || s === "") return 0;
  const n = parseInt(s, 10);
  if (!Number.isFinite(n) || n < 0) return 0;
  return n;
}

/**
 * Resolve workspace-relative `metadata.path` to a file URI using `workspaceFolderIndex`
 * (0-based; default 0). Returns `undefined` if the folder index is out of range or path looks unsafe.
 */
export function metadataToUri(
  workspaceFolders: readonly vscode.WorkspaceFolder[] | undefined,
  metadata: MossMetadata
): vscode.Uri | undefined {
  if (!workspaceFolders?.length) return undefined;

  const idx = parseWorkspaceFolderIndex(metadata.workspaceFolderIndex);
  if (idx >= workspaceFolders.length) return undefined;

  const rel = metadata.path?.replace(/\\/g, "/") ?? "";
  if (rel === "" || rel.startsWith("/")) return undefined;

  const segments = rel.split("/").filter((p) => p.length > 0);
  if (segments.some((p) => p === "..")) return undefined;

  const root = workspaceFolders[idx]!.uri;
  return segments.length === 0 ? root : vscode.Uri.joinPath(root, ...segments);
}

/**
 * Map 1-based inclusive line metadata to a VS Code `Range` (0-based lines).
 */
export function metadataToRange(metadata: MossMetadata): vscode.Range {
  const startLine = parsePositiveInt(metadata.startLine, 1);
  let endLine = parsePositiveInt(metadata.endLine, startLine);
  if (endLine < startLine) endLine = startLine;

  const start = startLine - 1;
  const end = endLine - 1;
  return new vscode.Range(start, 0, end, Number.MAX_SAFE_INTEGER);
}
