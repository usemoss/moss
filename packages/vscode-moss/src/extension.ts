import * as vscode from "vscode";
import {
  deleteCredentialsForWorkspace,
  readCredentialsBlob,
  storeCredentialsForWorkspace,
} from "./config.js";
import { runIndexWorkspace } from "./indexWorkspace.js";
import { registerSearchIndexStaleHandler } from "./mossQueryState.js";
import { registerMossStatusBar } from "./mossStatusBar.js";
import { MossSearchViewProvider } from "./searchViewProvider.js";

/**
 * Focus the Settings UI on Moss options. Cursor (and some VS Code builds) ignore the
 * **string** query passed to `openSettings2`; the supported shape is `{ query: string }`.
 * See https://github.com/microsoft/vscode/issues/226071
 * Fallback: `vscode://settings/<key>` reveals a contributed setting (same scheme in Cursor).
 */
async function revealMossSettings(): Promise<void> {
  try {
    await vscode.commands.executeCommand("workbench.action.openSettings2", {
      query: "moss.",
    });
    return;
  } catch {
    /* fall through */
  }
  try {
    await vscode.commands.executeCommand(
      "workbench.action.openSettings2",
      "moss."
    );
    return;
  } catch {
    /* fall through */
  }
  try {
    await vscode.commands.executeCommand(
      "workbench.action.openSettings",
      "moss."
    );
    return;
  } catch {
    /* fall through */
  }
  const opened = await vscode.env.openExternal(
    vscode.Uri.parse("vscode://settings/moss.indexName")
  );
  if (!opened) {
    await vscode.commands.executeCommand("workbench.action.openSettings");
  }
}

// ── Activation ───────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
  const log = vscode.window.createOutputChannel("Moss");

  registerMossStatusBar(context);

  // Sidebar search view
  const searchProvider = new MossSearchViewProvider(
    context.extensionUri,
    context,
    log
  );
  context.subscriptions.push(
    registerSearchIndexStaleHandler(() => searchProvider.resetSearchSession())
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      const mossKeysAffectingSession = [
        "moss.indexName",
        "moss.topK",
        "moss.alpha",
        "moss.modelId",
        "moss.includeGlob",
        "moss.excludeGlob",
        "moss.respectGitignore",
        "moss.maxFileSizeBytes",
        "moss.chunkMaxLines",
        "moss.chunkOverlapLines",
      ] as const;
      if (mossKeysAffectingSession.some((k) => e.affectsConfiguration(k))) {
        searchProvider.resetSearchSession();
      }
    })
  );

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      MossSearchViewProvider.viewId,
      searchProvider
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("moss.indexWorkspace", async () => {
      await runIndexWorkspace(context, log);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("moss.openSettings", () => {
      void revealMossSettings();
    })
  );

  // moss.search — focus the sidebar search view
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.search", async () => {
      await vscode.commands.executeCommand(
        "workbench.view.extension.mossContainer"
      );
      await vscode.commands.executeCommand("moss.searchView.focus");
    })
  );

  // moss.configureCredentials — prompt project ID then key (one pair per workspace blob)
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.configureCredentials", async () => {
      const folders = vscode.workspace.workspaceFolders;
      if (!folders?.length) {
        void vscode.window.showWarningMessage(
          "Moss: Open a folder or workspace before configuring credentials."
        );
        return;
      }
      const primary = folders[0]!;

      const currentId =
        (await readCredentialsBlob(context.secrets, primary))?.projectId ??
        process.env.MOSS_PROJECT_ID?.trim() ??
        "";

      const projectId = await vscode.window.showInputBox({
        title: "Moss — project credentials",
        prompt: "Project ID",
        value: currentId,
        ignoreFocusOut: true,
        placeHolder: "Your Moss project ID",
      });
      if (projectId === undefined) return;

      const trimmedId = projectId.trim();
      if (!trimmedId) {
        void vscode.window.showWarningMessage(
          "Moss: Project ID is required."
        );
        return;
      }

      const projectKeyInput = await vscode.window.showInputBox({
        title: "Moss — project credentials",
        prompt: "Project key",
        password: true,
        ignoreFocusOut: true,
        placeHolder: "Your Moss project key",
      });
      if (projectKeyInput === undefined) return;

      const trimmedKey = projectKeyInput.trim();
      if (!trimmedKey) {
        void vscode.window.showWarningMessage(
          "Moss: Project key is required. Run “Moss: Clear credentials” to remove stored credentials."
        );
        return;
      }

      await storeCredentialsForWorkspace(context.secrets, primary, {
        projectId: trimmedId,
        projectKey: trimmedKey,
      });

      searchProvider.resetSearchSession();

      void vscode.window.showInformationMessage(
        "Moss: Credentials saved for this workspace (secure storage)."
      );
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("moss.clearCredentials", async () => {
      const folders = vscode.workspace.workspaceFolders;
      if (!folders?.length) {
        void vscode.window.showWarningMessage(
          "Moss: Open a folder or workspace first."
        );
        return;
      }
      const primary = folders[0]!;
      await deleteCredentialsForWorkspace(context.secrets, primary);
      searchProvider.resetSearchSession();
      void vscode.window.showInformationMessage(
        "Moss: Workspace credentials removed from secure storage."
      );
    })
  );

  context.subscriptions.push(log);
}

export function deactivate(): void {}
