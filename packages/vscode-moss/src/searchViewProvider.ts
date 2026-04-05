import * as vscode from "vscode";
import { hitToRowDto, runMossQuery } from "./runMossQuery.js";
import { metadataToRange, metadataToUri } from "./paths.js";
import type { SearchHit } from "./types.js";

export class MossSearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "moss.searchView";

  private _view?: vscode.WebviewView;
  private _lastHits: SearchHit[] = [];
  private _querySeq = 0;

  constructor(
    private readonly _extensionUri: vscode.Uri,
    private readonly _context: vscode.ExtensionContext,
    private readonly _log: vscode.OutputChannel
  ) {}

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

    this._context.subscriptions.push(
      webviewView.webview.onDidReceiveMessage((message) => {
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
      })
    );
  }

  private async _handleQuery(text: string): Promise<void> {
    const webview = this._view?.webview;
    if (!webview) return;

    if (text === "") {
      webview.postMessage({
        type: "error",
        code: "QUERY_FAILED",
        message: "Enter a search query.",
      });
      return;
    }

    const seq = ++this._querySeq;
    webview.postMessage({ type: "loading", loading: true });
    webview.postMessage({ type: "clearError" });

    const result = await runMossQuery(this._context, text, this._log);

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
      font-weight: 600;
      font-size: 0.92em;
      word-break: break-all;
      margin-bottom: 4px;
    }
    .result-sub {
      font-size: 0.82em;
      color: var(--vscode-descriptionForeground);
      margin-bottom: 6px;
    }
    .result-snippet {
      font-size: 0.88em;
      line-height: 1.45;
      color: var(--vscode-foreground);
      opacity: 0.95;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      overflow: hidden;
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
    <ul class="result-list" id="resultList" style="display:none;"></ul>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const input = document.getElementById('query');
    const btn = document.getElementById('searchBtn');
    const meta = document.getElementById('meta');
    const errorBanner = document.getElementById('errorBanner');
    const emptyBlock = document.getElementById('emptyBlock');
    const emptyState = document.getElementById('emptyState');
    const resultList = document.getElementById('resultList');
    const mossSettingsLink = document.getElementById('mossSettingsLink');

    function openSettingsClick(e) {
      e.preventDefault();
      vscode.postMessage({ type: 'openMossSettings' });
    }
    mossSettingsLink.addEventListener('click', openSettingsClick);
    mossSettingsLink.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') openSettingsClick(e);
    });

    function setLoading(loading) {
      input.disabled = loading;
      btn.disabled = loading;
      btn.textContent = loading ? 'Searching…' : 'Search';
    }

    function showError(message) {
      errorBanner.textContent = message;
      errorBanner.classList.add('visible');
    }

    function clearError() {
      errorBanner.textContent = '';
      errorBanner.classList.remove('visible');
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }

    function submitQuery() {
      if (input.disabled) return;
      const text = input.value.trim();
      clearError();
      vscode.postMessage({ type: 'query', text });
    }

    btn.addEventListener('click', submitQuery);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitQuery();
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg || typeof msg.type !== 'string') return;

      if (msg.type === 'loading') {
        setLoading(!!msg.loading);
        if (msg.loading) {
          meta.textContent = '';
          resultList.innerHTML = '';
          resultList.style.display = 'none';
          emptyBlock.style.display = 'none';
        }
        return;
      }

      if (msg.type === 'clearError') {
        clearError();
        return;
      }

      if (msg.type === 'error') {
        showError(msg.message || 'Search failed.');
        resultList.style.display = 'none';
        resultList.innerHTML = '';
        emptyBlock.style.display = 'block';
        emptyState.innerHTML =
          'Could not complete this search. Fix the issue above, then try again.';
        return;
      }

      if (msg.type === 'results') {
        const hits = Array.isArray(msg.hits) ? msg.hits : [];
        if (hits.length === 0) {
          emptyBlock.style.display = 'block';
          emptyState.innerHTML = 'No results. Try different wording or run <strong>Moss: Index Workspace</strong>.';
          resultList.style.display = 'none';
          resultList.innerHTML = '';
          const t = typeof msg.timeMs === 'number' ? msg.timeMs + ' ms' : '';
          meta.textContent = t ? '0 results · ' + t : '0 results';
          return;
        }

        emptyBlock.style.display = 'none';
        resultList.style.display = 'flex';
        resultList.innerHTML = hits.map((h) => {
          const path = escapeHtml(h.path || '');
          const line = escapeHtml(String(h.lineLabel ?? ''));
          const score = typeof h.score === 'number' ? h.score.toFixed(3) : '';
          const snippet = escapeHtml(h.snippet || '');
          return (
            '<li class="result-row" data-hit-index="' + h.index + '">' +
              '<div class="result-path">' + path + '</div>' +
              '<div class="result-sub">Lines ' + line + (score ? ' · score ' + escapeHtml(score) : '') + '</div>' +
              '<div class="result-snippet">' + snippet + '</div>' +
            '</li>'
          );
        }).join('');

        resultList.querySelectorAll('.result-row').forEach((el) => {
          el.addEventListener('click', () => {
            const idx = parseInt(el.getAttribute('data-hit-index'), 10);
            if (!Number.isNaN(idx)) {
              vscode.postMessage({ type: 'openResult', hitIndex: idx });
            }
          });
        });

        const t = typeof msg.timeMs === 'number' ? msg.timeMs + ' ms' : '';
        meta.textContent = hits.length + ' result' + (hits.length === 1 ? '' : 's') + (t ? ' · ' + t : '');
        return;
      }
    });
  </script>
</body>
</html>`;
  }
}

async function openSearchHit(hit: SearchHit): Promise<void> {
  const folders = vscode.workspace.workspaceFolders;
  const uri = metadataToUri(folders, hit.metadata);
  if (!uri) {
    void vscode.window.showWarningMessage(
      "Moss: Could not resolve file location for this result."
    );
    return;
  }

  try {
    const doc = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(doc, { preview: true });
    const range = metadataToRange(hit.metadata);
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
