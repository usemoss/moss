import { MossClient, type QueryResultDocumentInfo } from "@moss-dev/moss";
import * as vscode from "vscode";
import { getMossConfig, resolveCredentials } from "./config.js";
import { ensureLocalIndexLoaded, clearLocalIndexLoadState, type LocalIndexLoadState } from "./mossQueryState.js";
import { mossLog } from "./mossLog.js";
import { hitToRowDto, runMossQuery } from "./runMossQuery.js";
import { metadataToRange, metadataToUri } from "./paths.js";

export class MossSearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "moss.searchView";

  private _view?: vscode.WebviewView;
  private _lastHits: QueryResultDocumentInfo[] = [];
  private _querySeq = 0;
  private _session?: {
    projectId: string;
    projectKey: string;
    client: MossClient;
  };
  private _localIndexState: LocalIndexLoadState = {};
  private _webviewMessageDisposable?: vscode.Disposable;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _context: vscode.ExtensionContext,
    private readonly _log: vscode.OutputChannel
  ) {}

  /** Drop Moss client + local `loadIndex` state (sidebar closed, credentials changed, or index rebuilt). */
  public resetSearchSession(): void {
    this._session = undefined;
    clearLocalIndexLoadState(this._localIndexState);
  }

  private _clientFor(projectId: string, projectKey: string): MossClient {
    if (
      this._session?.projectId === projectId &&
      this._session?.projectKey === projectKey
    ) {
      return this._session.client;
    }
    this._session = {
      projectId,
      projectKey,
      client: new MossClient(projectId, projectKey),
    };
    clearLocalIndexLoadState(this._localIndexState);
    return this._session.client;
  }

  private async _warmLocalIndex(token: vscode.CancellationToken): Promise<void> {
    if (token.isCancellationRequested) return;
    const folders = vscode.workspace.workspaceFolders;
    if (!folders?.length) return;
    const creds = await resolveCredentials(this._context);
    if (!creds) return;
    const cfg = await getMossConfig(this._context.secrets, folders[0]!);
    if (token.isCancellationRequested) return;
    try {
      const client = this._clientFor(creds.projectId, creds.projectKey);
      await ensureLocalIndexLoaded(client, cfg.indexName, this._localIndexState);
      mossLog(this._log, "Moss: Sidebar index warm-up finished.", "verbose");
    } catch (e: unknown) {
      if (token.isCancellationRequested) return;
      const msg = e instanceof Error ? e.message : String(e);
      mossLog(
        this._log,
        `Moss: Sidebar index warm-up failed; local loadIndex skipped for this session (cloud fallback). ${msg}`,
        "verbose"
      );
    }
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };

    webviewView.webview.html = this._getHtml(webviewView.webview);

    const warmCts = new vscode.CancellationTokenSource();
    webviewView.onDidDispose(() => {
      this._webviewMessageDisposable?.dispose();
      this._webviewMessageDisposable = undefined;
      this._view = undefined;
      warmCts.cancel();
      warmCts.dispose();
      this.resetSearchSession();
    });

    this._webviewMessageDisposable?.dispose();
    this._webviewMessageDisposable = webviewView.webview.onDidReceiveMessage(
      (message) => {
        switch (message.type) {
          case "query":
            if (typeof message.text === "string") {
              void this._handleQuery(message.text.trim());
            }
            break;
          case "openResult":
            if (typeof message.hitIndex === "number") {
              void this._openHitAtIndex(message.hitIndex);
            }
            break;
          case "openMossSettings":
            void vscode.commands.executeCommand("moss.openSettings");
            break;
          default:
            break;
        }
      }
    );

    void this._warmLocalIndex(warmCts.token);
  }

  private async _handleQuery(text: string): Promise<void> {
    const webview = this._view?.webview;
    if (!webview) return;

    if (text === "") {
      webview.postMessage({ type: "clearResults" });
      return;
    }

    const seq = ++this._querySeq;
    webview.postMessage({ type: "loading", loading: true });
    webview.postMessage({ type: "clearError" });

    const creds = await resolveCredentials(this._context);
    if (!creds) {
      if (seq !== this._querySeq) return;
      webview.postMessage({ type: "loading", loading: false });
      webview.postMessage({
        type: "error",
        code: "NO_CREDENTIALS",
        message:
          "Missing Moss credentials. Run “Moss: Configure credentials” or set MOSS_PROJECT_ID / MOSS_PROJECT_KEY.",
      });
      return;
    }

    const client = this._clientFor(creds.projectId, creds.projectKey);
    const result = await runMossQuery(
      this._context,
      text,
      this._log,
      { client, localIndexState: this._localIndexState },
      {
        onAwaitingLocalIndexDownload: () => {
          webview.postMessage({
            type: "localIndexLoading",
            text: "Downloading index for local search — first time can take a minute…",
          });
        },
        onLocalIndexDownloadFinished: () => {
          webview.postMessage({ type: "localIndexLoading", text: "" });
        },
      }
    );

    if (seq !== this._querySeq) return;

    webview.postMessage({ type: "loading", loading: false });

    if (!result.ok) {
      webview.postMessage({
        type: "error",
        code: result.error.code,
        message: result.error.message,
      });
      return;
    }

    this._lastHits = result.hits;
    webview.postMessage({
      type: "results",
      query: text,
      hits: result.hits.map((h, index) => ({
        index,
        ...hitToRowDto(h),
      })),
      timeMs: result.timeMs,
    });
  }

  private async _openHitAtIndex(hitIndex: number): Promise<void> {
    if (hitIndex < 0 || hitIndex >= this._lastHits.length) return;
    const hit = this._lastHits[hitIndex]!;
    await openSearchHit(hit);
  }

  private _getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this._extensionUri, "media", "searchView.js")
    );
    const csp = [
      "default-src 'none'",
      `style-src 'nonce-${nonce}' ${webview.cspSource}`,
      `script-src 'nonce-${nonce}' ${webview.cspSource}`,
    ].join("; ");

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style nonce="${nonce}">
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      padding: 10px 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 100%;
    }
    .search-box {
      display: flex;
      gap: 6px;
      flex-shrink: 0;
    }
    .search-box input {
      flex: 1;
      min-width: 0;
      padding: 5px 8px;
      border: 1px solid var(--vscode-input-border, transparent);
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border-radius: 2px;
      outline: none;
      font-size: inherit;
      font-family: inherit;
    }
    .search-box input:focus {
      border-color: var(--vscode-focusBorder);
    }
    .search-box input::placeholder {
      color: var(--vscode-input-placeholderForeground);
    }
    .search-box input:disabled {
      opacity: 0.65;
      cursor: not-allowed;
    }
    .search-box button {
      padding: 5px 12px;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 2px;
      cursor: pointer;
      font-size: inherit;
      font-family: inherit;
      white-space: nowrap;
    }
    .search-box button:hover:not(:disabled) {
      background: var(--vscode-button-hoverBackground);
    }
    .search-box button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    .meta-row {
      font-size: 0.85em;
      color: var(--vscode-descriptionForeground);
      min-height: 1.2em;
    }
    .index-prep {
      display: none;
      font-size: 0.88em;
      color: var(--vscode-descriptionForeground);
      line-height: 1.45;
    }
    .index-prep.visible { display: block; }
    .error-banner {
      display: none;
      padding: 8px 10px;
      border-radius: 4px;
      background: var(--vscode-inputValidation-errorBackground);
      color: var(--vscode-inputValidation-errorForeground);
      border: 1px solid var(--vscode-inputValidation-errorBorder);
      font-size: 0.9em;
      line-height: 1.45;
    }
    .error-banner.visible { display: block; }
    #results {
      flex: 1;
      min-height: 120px;
      overflow-y: auto;
    }
    .empty-state {
      color: var(--vscode-descriptionForeground);
      font-size: 0.9em;
      line-height: 1.6;
      text-align: center;
      margin-top: 20px;
      padding: 0 8px;
    }
    .result-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .result-row {
      border: 1px solid var(--vscode-widget-border, rgba(128,128,128,0.35));
      border-radius: 4px;
      padding: 8px 10px;
      cursor: pointer;
      background: var(--vscode-editor-inactiveSelectionBackground, rgba(128,128,128,0.12));
    }
    .result-row:hover {
      background: var(--vscode-list-hoverBackground);
      color: var(--vscode-list-hoverForeground, var(--vscode-foreground));
    }
    .result-path {
      font-size: 0.92em;
      line-height: 1.35;
      word-break: break-all;
      margin-bottom: 4px;
    }
    .result-dir {
      font-weight: 400;
      color: var(--vscode-descriptionForeground);
      font-size: 0.92em;
    }
    .result-base {
      font-weight: 600;
      color: var(--vscode-foreground);
    }
    .result-sub {
      font-size: 0.82em;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 6px;
    }
    .result-snippet {
      font-family: var(--vscode-editor-font-family);
      font-size: calc(var(--vscode-font-size) * 0.92);
      line-height: 1.45;
      color: var(--vscode-foreground);
      opacity: 0.95;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    mark.query-hit {
      background: var(
        --vscode-editor-findMatchHighlightBackground,
        rgba(234, 92, 0, 0.28)
      );
      color: inherit;
      padding: 0 0.05em;
      border-radius: 2px;
    }
    .result-row--selected {
      outline: 1px solid var(--vscode-focusBorder);
      outline-offset: -1px;
    }
    .settings-hint {
      margin-top: 14px;
      text-align: center;
    }
    .settings-link {
      color: var(--vscode-textLink-foreground);
      cursor: pointer;
      font-size: 0.88em;
      text-decoration: underline;
    }
    .settings-link:hover {
      color: var(--vscode-textLink-activeForeground);
    }
    .settings-link:focus {
      outline: 1px solid var(--vscode-focusBorder);
      outline-offset: 2px;
    }
  </style>
</head>
<body>
  <div class="search-box">
    <input type="text" id="query" placeholder="Search your codebase…" />
    <button id="searchBtn">Search</button>
  </div>
  <div class="meta-row" id="meta"></div>
  <div class="index-prep" id="indexPrep" role="status" aria-live="polite"></div>
  <div class="error-banner" id="errorBanner" role="alert"></div>
  <div id="results">
    <div id="emptyBlock">
      <p class="empty-state" id="emptyState">
        Run <strong>Moss: Index Workspace</strong> to index your files,<br/>
        then search here.
      </p>
      <p class="settings-hint">
        <a href="#" id="mossSettingsLink" class="settings-link" role="button" tabindex="0">Open Moss settings</a>
      </p>
    </div>
    <ul class="result-list" id="resultList" style="display:none;" role="listbox" aria-label="Search results"></ul>
  </div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

async function openSearchHit(hit: QueryResultDocumentInfo): Promise<void> {
  const folders = vscode.workspace.workspaceFolders;
  const meta = hit.metadata ?? {};
  const uri = metadataToUri(folders, meta);
  if (!uri) {
    void vscode.window.showWarningMessage(
      "Moss: Could not resolve file location for this result."
    );
    return;
  }

  try {
    const doc = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(doc, { preview: true });
    const range = metadataToRange(meta);
    const start = range.start;
    editor.selection = new vscode.Selection(start, start);
    editor.revealRange(
      range,
      vscode.TextEditorRevealType.InCenterIfOutsideViewport
    );
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    void vscode.window.showErrorMessage(`Moss: Could not open file: ${msg}`);
  }
}

function getNonce(): string {
  const chars =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}
