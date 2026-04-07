import type { MossClient, QueryResultDocumentInfo } from "@moss-dev/moss";
import * as vscode from "vscode";
import { getMossConfig, resolveCredentials } from "./config.js";
import { ensureLocalIndexLoaded, type LocalIndexLoadState } from "./mossQueryState.js";
import { mossLog } from "./mossLog.js";

export type SearchErrorCode =
  | "NO_WORKSPACE"
  | "NO_CREDENTIALS"
  | "INDEX_NOT_FOUND"
  | "QUERY_FAILED";

export interface SearchFailure {
  code: SearchErrorCode;
  message: string;
}

function formatError(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function lineLabel(meta: Record<string, string>): string {
  const start = meta.startLine?.trim() ?? "";
  const end = meta.endLine?.trim() ?? "";
  if (start && end && start !== end) return `${start}–${end}`;
  if (start) return start;
  return "?";
}

export interface RunMossQueryHooks {
  /** Called immediately before a blocking `loadIndex` (first local search or after cache invalidation). */
  onAwaitingLocalIndexDownload?: () => void;
  /** Called after `loadIndex` finishes or throws (before `query` runs). */
  onLocalIndexDownloadFinished?: () => void;
}

export interface MossQuerySession {
  client: MossClient;
  localIndexState: LocalIndexLoadState;
}

/**
 * Semantic search against the configured workspace index.
 * Uses `session` for the Moss client and local `loadIndex` state (sidebar search lifetime).
 */
export async function runMossQuery(
  context: vscode.ExtensionContext,
  queryText: string,
  log: vscode.OutputChannel,
  session: MossQuerySession,
  hooks?: RunMossQueryHooks
): Promise<
  | { ok: true; hits: QueryResultDocumentInfo[]; timeMs?: number }
  | { ok: false; error: SearchFailure }
> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders?.length) {
    return {
      ok: false,
      error: {
        code: "NO_WORKSPACE",
        message: "Open a folder or workspace before searching.",
      },
    };
  }

  const creds = await resolveCredentials(context);
  if (!creds) {
    return {
      ok: false,
      error: {
        code: "NO_CREDENTIALS",
        message:
          "Missing Moss credentials. Run “Moss: Configure credentials” or set MOSS_PROJECT_ID / MOSS_PROJECT_KEY.",
      },
    };
  }

  const primary = folders[0]!;
  const cfg = await getMossConfig(context.secrets, primary);
  const sdk = session.client;

  const state = session.localIndexState;
  const willAttemptLocalLoad =
    state.loadedIndexName !== cfg.indexName &&
    state.localLoadFailedIndex !== cfg.indexName;

  if (willAttemptLocalLoad) {
    hooks?.onAwaitingLocalIndexDownload?.();
  }
  try {
    await ensureLocalIndexLoaded(sdk, cfg.indexName, state);
  } catch (e: unknown) {
    mossLog(
      log,
      `Moss: Search — loadIndex failed; continuing with cloud query. ${formatError(e)}`,
      "verbose"
    );
  } finally {
    if (willAttemptLocalLoad) {
      hooks?.onLocalIndexDownloadFinished?.();
    }
  }

  try {
    const result = await sdk.query(cfg.indexName, queryText, {
      topK: cfg.topK,
      alpha: cfg.alpha,
    });

    const hits: QueryResultDocumentInfo[] = result.docs.map((d) => ({
      ...d,
      metadata: { ...(d.metadata ?? {}) },
    }));

    return { ok: true, hits, timeMs: result.timeTakenInMs };
  } catch (e: unknown) {
    const msg = formatError(e);
    const lower = msg.toLowerCase();
    if (
      /not found|does not exist|no such index|unknown index|index.*missing/i.test(
        lower
      )
    ) {
      return {
        ok: false,
        error: {
          code: "INDEX_NOT_FOUND",
          message: `Index “${cfg.indexName}” was not found. Run “Moss: Index Workspace” first.`,
        },
      };
    }
    return {
      ok: false,
      error: { code: "QUERY_FAILED", message: msg },
    };
  }
}

export function hitToRowDto(hit: QueryResultDocumentInfo): {
  path: string;
  lineLabel: string;
  score: number;
  snippet: string;
} {
  const meta = hit.metadata ?? {};
  const path = meta.path?.replace(/\\/g, "/") ?? hit.id;
  const snippet = truncateSnippet(hit.text, 280);
  return {
    path,
    lineLabel: lineLabel(meta),
    score: hit.score,
    snippet,
  };
}

function truncateSnippet(text: string, maxLen: number): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}
