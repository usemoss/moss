import * as vscode from "vscode";
import { MossRestClient } from "@inferedge-rest/moss";
import { MossClient } from "@inferedge/moss";

const SPIKE_INDEX_NAME = "vscode-moss-phase1-spike";
const SPIKE_MODEL_ID = "moss-minilm";
const OUTPUT_CHANNEL_ID = "moss-spike";

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

function getCredentials(): { projectId: string; projectKey: string } | undefined {
  const fromEnv =
    process.env.MOSS_PROJECT_ID && process.env.MOSS_PROJECT_KEY
      ? {
          projectId: process.env.MOSS_PROJECT_ID,
          projectKey: process.env.MOSS_PROJECT_KEY,
        }
      : undefined;
  if (fromEnv) {
    return fromEnv;
  }
  const cfg = vscode.workspace.getConfiguration("moss");
  const projectId = cfg.get<string>("projectId")?.trim();
  const projectKey = cfg.get<string>("projectKey")?.trim();
  if (projectId && projectKey) {
    return { projectId, projectKey };
  }
  return undefined;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function tolerateDeleteIndex(
  client: MossRestClient,
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

export function activate(context: vscode.ExtensionContext): void {
  const log = vscode.window.createOutputChannel(OUTPUT_CHANNEL_ID);

  const disposable = vscode.commands.registerCommand(
    "moss.spikeConnectivity",
    async () => {
      log.clear();
      log.show(true);
      log.appendLine("Moss Phase 1 spike — starting…");

      const creds = getCredentials();
      if (!creds) {
        const msg =
          "Missing Moss credentials. Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in the environment " +
          "(e.g. launch.json for F5), or add moss.projectId / moss.projectKey in Settings.";
        log.appendLine(msg);
        void vscode.window.showErrorMessage(msg);
        return;
      }

      const rest = new MossRestClient(creds.projectId, creds.projectKey);
      const sdk = new MossClient(creds.projectId, creds.projectKey);

      try {
        log.appendLine("Step 1: REST deleteIndex (tolerate missing)…");
        await tolerateDeleteIndex(rest, SPIKE_INDEX_NAME, log);

        log.appendLine("Step 2: REST createIndex with 3 documents…");
        await rest.createIndex(SPIKE_INDEX_NAME, SPIKE_DOCS, SPIKE_MODEL_ID);
        log.appendLine("createIndex completed.");

        log.appendLine("Step 3: Brief pause for index readiness…");
        await sleep(2500);

        let localQueryMs: number | undefined;
        let localError: string | undefined;

        log.appendLine("Step 4: SDK loadIndex…");
        try {
          await sdk.loadIndex(SPIKE_INDEX_NAME);
          log.appendLine("loadIndex succeeded.");

          log.appendLine('Step 5: SDK query (local) — "refund policy"…');
          const localResult = await sdk.query(SPIKE_INDEX_NAME, "refund policy", {
            topK: 2,
          });
          localQueryMs = localResult.timeTakenInMs;
          log.appendLine(
            `Local query: ${localResult.docs.length} docs in ${localQueryMs ?? "?"} ms`
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
            "Falling back to cloud query (no loadIndex) — see PHASE1_SPIKE.md if this persists."
          );

          log.appendLine('Step 5b: SDK query (cloud fallback) — "refund policy"…');
          const cloudResult = await sdk.query(SPIKE_INDEX_NAME, "refund policy", {
            topK: 2,
          });
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
    }
  );

  context.subscriptions.push(disposable, log);
}

export function deactivate(): void {}
