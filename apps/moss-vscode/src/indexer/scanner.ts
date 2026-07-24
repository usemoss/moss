import * as fs from "node:fs/promises";
import * as path from "node:path";
import ignore from "ignore";
import * as vscode from "vscode";
import { getExcludeGlobs, getIncludeGlobs } from "../moss/config";
import { isExcludedFromIndex } from "./excludes";

const MAX_FILE_BYTES = 512 * 1024;

async function loadGitignore(root: string): Promise<ReturnType<typeof ignore> | undefined> {
  try {
    const raw = await fs.readFile(path.join(root, ".gitignore"), "utf8");
    return ignore().add(raw);
  } catch {
    return undefined;
  }
}

function matchesAnyGlob(relativePath: string, globs: string[]): boolean {
  // vscode.RelativePattern handles brace expansion via findFiles; here we
  // approximate with simple extension / segment checks for post-filtering.
  return globs.some((glob) => {
    const brace = glob.match(/\{([^}]+)\}/);
    if (brace) {
      const exts = brace[1].split(",");
      const ext = path.extname(relativePath).replace(".", "");
      return exts.includes(ext);
    }
    return relativePath.endsWith(glob.replace("**/", ""));
  });
}

export async function scanWorkspaceFiles(
  token?: vscode.CancellationToken,
): Promise<vscode.Uri[]> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return [];
  }

  const includeGlobs = getIncludeGlobs();
  const excludeGlobs = getExcludeGlobs();
  const exclude = `{${excludeGlobs.join(",")}}`;
  const results: vscode.Uri[] = [];

  for (const folder of folders) {
    if (token?.isCancellationRequested) {
      break;
    }

    const gitignore = await loadGitignore(folder.uri.fsPath);

    for (const include of includeGlobs) {
      if (token?.isCancellationRequested) {
        break;
      }
      const pattern = new vscode.RelativePattern(folder, include);
      const found = await vscode.workspace.findFiles(pattern, exclude, undefined, token);
      for (const uri of found) {
        const rel = path.relative(folder.uri.fsPath, uri.fsPath).split(path.sep).join("/");
        if (isExcludedFromIndex(rel)) {
          continue;
        }
        if (gitignore?.ignores(rel)) {
          continue;
        }
        results.push(uri);
      }
    }
  }

  // De-dupe
  const seen = new Set<string>();
  return results.filter((uri) => {
    const key = uri.toString();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export async function readFileForIndex(
  uri: vscode.Uri,
): Promise<{ relativePath: string; content: string } | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return undefined;
  }

  let relativePath = uri.fsPath;
  for (const folder of folders) {
    if (uri.fsPath.startsWith(folder.uri.fsPath)) {
      relativePath = path
        .relative(folder.uri.fsPath, uri.fsPath)
        .split(path.sep)
        .join("/");
      break;
    }
  }

  try {
    const stat = await fs.stat(uri.fsPath);
    if (!stat.isFile() || stat.size > MAX_FILE_BYTES) {
      return undefined;
    }
    const content = await fs.readFile(uri.fsPath, "utf8");
    // Skip likely-binary content
    if (content.includes("\u0000")) {
      return undefined;
    }
    return { relativePath, content };
  } catch {
    return undefined;
  }
}

export function toWorkspaceRelative(uri: vscode.Uri): string {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return uri.fsPath;
  }
  for (const folder of folders) {
    if (uri.fsPath.startsWith(folder.uri.fsPath)) {
      return path
        .relative(folder.uri.fsPath, uri.fsPath)
        .split(path.sep)
        .join("/");
    }
  }
  return uri.fsPath;
}

// Keep helper referenced for potential future include filtering
void matchesAnyGlob;
