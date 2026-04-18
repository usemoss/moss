import ignore from "ignore";
import * as vscode from "vscode";

/**
 * Drop URIs whose path matches the **workspace-folder root** `.gitignore`,
 * using the same matching rules as Git for that file (via the `ignore` package).
 * Nested `.gitignore` files in subdirectories are not read (same patterns often
 * appear in the root file in monorepos).
 */
export async function filterUrisByRootGitignore(
  uris: vscode.Uri[],
  folders: readonly vscode.WorkspaceFolder[]
): Promise<vscode.Uri[]> {
  if (uris.length === 0) return uris;

  const igByFolderUri = new Map<string, ReturnType<typeof ignore>>();
  await Promise.all(
    folders.map(async (folder) => {
      let ig = ignore();
      try {
        const giUri = vscode.Uri.joinPath(folder.uri, ".gitignore");
        const bytes = await vscode.workspace.fs.readFile(giUri);
        let text = new TextDecoder("utf-8").decode(bytes);
        if (text.charCodeAt(0) === 0xfeff) {
          text = text.slice(1);
        }
        ig = ignore().add(text);
      } catch {
        // Missing or unreadable `.gitignore` → no extra excludes.
      }
      igByFolderUri.set(folder.uri.toString(), ig);
    })
  );

  return uris.filter((uri) => {
    const folder = vscode.workspace.getWorkspaceFolder(uri);
    if (!folder) return true;
    const ig = igByFolderUri.get(folder.uri.toString());
    if (!ig) return true;

    const rel = vscode.workspace.asRelativePath(uri, false);
    if (!rel) return true;
    const posix = rel.replace(/\\/g, "/");
    return !ig.ignores(posix);
  });
}
