import * as vscode from "vscode";
import {
  MOSS_SECRET_KEY_PROJECT_KEY,
} from "./config.js";
import { runIndexWorkspace } from "./indexWorkspace.js";
import { registerSearchIndexStaleHandler } from "./mossQueryState.js";
import { registerMossStatusBar } from "./mossStatusBar.js";
import { MossSearchViewProvider } from "./searchViewProvider.js";

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
        "moss.projectId",
        "moss.projectKey",
        "moss.indexName",
        "moss.topK",
        "moss.alpha",
        "moss.modelId",
        "moss.includeGlob",
        "moss.excludeGlob",
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
    vscode.commands.registerCommand("moss.openSettings", async () => {
      // Filter must match package.json publisher + name (moss-dev / vscode-moss).
      await vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "@ext:moss-dev.vscode-moss"
      );
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

  // moss.configureCredentials — QuickPick: full setup (ID + key) or key-only (empty clears)
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.configureCredentials", async () => {
      type CredAction = "idAndKey" | "keyOnly";
      interface CredPick extends vscode.QuickPickItem {
        action: CredAction;
      }
      const items: CredPick[] = [
        {
          label: "Project ID and project key",
          description: "Save project ID to settings; optionally set a new key",
          action: "idAndKey",
        },
        {
          label: "Project key only",
          description: "Update or clear the key in secure storage (empty input removes it)",
          action: "keyOnly",
        },
      ];
      const choice = await vscode.window.showQuickPick(items, {
        title: "Moss",
        placeHolder: "What do you want to configure?",
        ignoreFocusOut: true,
      });
      if (!choice) return;

      if (choice.action === "keyOnly") {
        const key = await vscode.window.showInputBox({
          title: "Moss",
          prompt: "Project key",
          password: true,
          ignoreFocusOut: true,
          placeHolder: "Leave empty to remove the key from secure storage",
        });
        if (key === undefined) return;
        if (key === "") {
          await context.secrets.delete(MOSS_SECRET_KEY_PROJECT_KEY);
          searchProvider.resetSearchSession();
          void vscode.window.showInformationMessage(
            "Moss: Project key removed from secure storage."
          );
        } else {
          await context.secrets.store(MOSS_SECRET_KEY_PROJECT_KEY, key);
          searchProvider.resetSearchSession();
          void vscode.window.showInformationMessage(
            "Moss: Project key saved to secure storage."
          );
        }
        return;
      }

      const cfg = vscode.workspace.getConfiguration("moss");
      const currentId = cfg.get<string>("projectId")?.trim() ?? "";

      const projectId = await vscode.window.showInputBox({
        title: "Moss",
        prompt: "Project ID",
        value: currentId,
        ignoreFocusOut: true,
        placeHolder: "Your Moss project id",
      });
      if (projectId === undefined) return;

      const trimmedId = projectId.trim();
      if (!trimmedId) {
        void vscode.window.showWarningMessage(
          "Moss: Project ID is required. Nothing was saved."
        );
        return;
      }

      const projectKey = await vscode.window.showInputBox({
        title: "Moss",
        prompt: "Project key",
        password: true,
        ignoreFocusOut: true,
        placeHolder: "Leave empty to keep the existing key in secure storage",
      });
      if (projectKey === undefined) return;

      const configTarget =
        vscode.workspace.workspaceFolders &&
        vscode.workspace.workspaceFolders.length > 0
          ? vscode.ConfigurationTarget.Workspace
          : vscode.ConfigurationTarget.Global;

      try {
        await cfg.update("projectId", trimmedId, configTarget);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        void vscode.window.showErrorMessage(
          `Moss: Could not save project ID: ${msg}`
        );
        return;
      }

      if (projectKey !== "") {
        await context.secrets.store(MOSS_SECRET_KEY_PROJECT_KEY, projectKey);
      }

      searchProvider.resetSearchSession();

      void vscode.window.showInformationMessage(
        projectKey !== ""
          ? "Moss: Project ID saved to settings and project key saved to secure storage."
          : "Moss: Project ID saved to settings. Project key unchanged."
      );
    })
  );

  context.subscriptions.push(log);
}

export function deactivate(): void {}
