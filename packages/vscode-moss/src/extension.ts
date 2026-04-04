import * as vscode from "vscode";
import {
  MOSS_SECRET_KEY_PROJECT_KEY,
  resolveCredentials,
} from "./config.js";
import { createRestClient, createSdkClient } from "./mossClients.js";
import { MossSearchViewProvider } from "./searchViewProvider.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Activation ───────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
  const log = vscode.window.createOutputChannel("Moss");

  // Sidebar search view
  const searchProvider = new MossSearchViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      MossSearchViewProvider.viewId,
      searchProvider
    )
  );

  // moss.indexWorkspace (placeholder — implementation in Phase 5)
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.indexWorkspace", async () => {
      void vscode.window.showInformationMessage(
        "Moss: Index Workspace is not yet implemented."
      );
    })
  );

  // moss.search — focus the sidebar search view
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.search", async () => {
      await vscode.commands.executeCommand("moss.searchView.focus");
    })
  );

  // moss.configureCredentials — project ID → settings; project key → SecretStorage
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.configureCredentials", async () => {
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

      void vscode.window.showInformationMessage(
        projectKey !== ""
          ? "Moss: Project ID saved to settings and project key saved to secure storage."
          : "Moss: Project ID saved to settings. Project key unchanged."
      );
    })
  );

  // moss.setApiKey — store / clear project key via SecretStorage
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.setApiKey", async () => {
      const key = await vscode.window.showInputBox({
        prompt: "Enter your Moss project key",
        password: true,
        ignoreFocusOut: true,
        placeHolder: "pk_…",
      });
      if (key !== undefined) {
        if (key === "") {
          await context.secrets.delete(MOSS_SECRET_KEY_PROJECT_KEY);
          void vscode.window.showInformationMessage(
            "Moss project key removed from secure storage."
          );
        } else {
          await context.secrets.store(MOSS_SECRET_KEY_PROJECT_KEY, key);
          void vscode.window.showInformationMessage(
            "Moss project key saved to secure storage."
          );
        }
      }
    })
  );

  // moss.spikeConnectivity (Phase 1 — retained for dev testing)
  registerSpikeCommand(context, log);

  context.subscriptions.push(log);
}

export function deactivate(): void {}

// ── Phase 1 spike command (temporary) ────────────────────────────────

const SPIKE_INDEX_NAME = "vscode-moss-phase1-spike";
const SPIKE_MODEL_ID = "moss-minilm";

const SPIKE_DOCS = [
  {
    id: "spike-1",
    text: "Moss VS Code extension Phase 1 connectivity spike document about semantic search.",
    metadata: { kind: "spike", idx: "1" },
  },
  {
    id: "spike-2",
    text: "Refunds are processed within three to five business days according to policy.",
    metadata: { kind: "spike", idx: "2" },
  },
  {
    id: "spike-3",
    text: "The vector runtime downloads embeddings for local sub-millisecond queries.",
    metadata: { kind: "spike", idx: "3" },
  },
];

async function tolerateDeleteIndex(
  client: ReturnType<typeof createRestClient>,
  indexName: string,
  log: vscode.OutputChannel
): Promise<void> {
  try {
    await client.deleteIndex(indexName);
    log.appendLine(`Deleted existing index "${indexName}" (if it existed).`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (/not found|does not exist/i.test(msg)) {
      log.appendLine(`No existing index "${indexName}" to delete (ok).`);
    } else {
      log.appendLine(`deleteIndex warning: ${msg}`);
    }
  }
}

function registerSpikeCommand(
  context: vscode.ExtensionContext,
  log: vscode.OutputChannel
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("moss.spikeConnectivity", async () => {
      log.clear();
      log.show(true);
      log.appendLine("Moss Phase 1 spike — starting…");

      const creds = await resolveCredentials(context);
      if (!creds) {
        const msg =
          "Missing Moss credentials. Run 'Moss: Configure credentials', or use 'Moss: Set API Key' " +
          "with moss.projectId in Settings, or set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in the environment.";
        log.appendLine(msg);
        void vscode.window.showErrorMessage(msg);
        return;
      }

      const rest = createRestClient(creds.projectId, creds.projectKey);
      const sdk = createSdkClient(creds.projectId, creds.projectKey);

      try {
        log.appendLine("Step 1: REST deleteIndex (tolerate missing)…");
        await tolerateDeleteIndex(rest, SPIKE_INDEX_NAME, log);

        log.appendLine("Step 2: REST createIndex with 3 documents…");
        await rest.createIndex(SPIKE_INDEX_NAME, SPIKE_DOCS, SPIKE_MODEL_ID);
        log.appendLine("createIndex completed.");

        log.appendLine("Step 3: Brief pause for index readiness…");
        await sleep(2500);

        let localError: string | undefined;

        log.appendLine("Step 4: SDK loadIndex…");
        try {
          await sdk.loadIndex(SPIKE_INDEX_NAME);
          log.appendLine("loadIndex succeeded.");

          log.appendLine('Step 5: SDK query (local) — "refund policy"…');
          const localResult = await sdk.query(
            SPIKE_INDEX_NAME,
            "refund policy",
            { topK: 2 }
          );
          log.appendLine(
            `Local query: ${localResult.docs.length} docs in ${localResult.timeTakenInMs ?? "?"} ms`
          );
          for (const d of localResult.docs) {
            log.appendLine(
              `  - id=${d.id} score=${d.score.toFixed(4)} text=${d.text.slice(0, 80)}…`
            );
          }
        } catch (e: unknown) {
          localError = e instanceof Error ? e.message : String(e);
          log.appendLine(`loadIndex/query (local path) failed: ${localError}`);
          log.appendLine(
            "Falling back to cloud query — see PHASE1_SPIKE.md if this persists."
          );

          log.appendLine('Step 5b: SDK query (cloud fallback) — "refund policy"…');
          const cloudResult = await sdk.query(
            SPIKE_INDEX_NAME,
            "refund policy",
            { topK: 2 }
          );
          log.appendLine(
            `Cloud query: ${cloudResult.docs.length} docs in ${cloudResult.timeTakenInMs ?? "?"} ms`
          );
          for (const d of cloudResult.docs) {
            log.appendLine(
              `  - id=${d.id} score=${d.score.toFixed(4)} text=${d.text.slice(0, 80)}…`
            );
          }
        }

        const summary =
          localError === undefined
            ? "Moss Phase 1 spike succeeded (local loadIndex + query)."
            : "Moss Phase 1 spike completed using cloud query fallback; check output for loadIndex error.";
        log.appendLine(summary);
        void vscode.window.showInformationMessage(summary);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        log.appendLine(`SPIKE FAILED: ${msg}`);
        void vscode.window.showErrorMessage(`Moss spike failed: ${msg}`);
      }
    })
  );
}
