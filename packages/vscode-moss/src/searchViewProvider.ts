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
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const input = document.getElementById('query');
    const btn = document.getElementById('searchBtn');
    const meta = document.getElementById('meta');
    const indexPrep = document.getElementById('indexPrep');
    const errorBanner = document.getElementById('errorBanner');
    const emptyBlock = document.getElementById('emptyBlock');
    const emptyState = document.getElementById('emptyState');
    const resultList = document.getElementById('resultList');
    const mossSettingsLink = document.getElementById('mossSettingsLink');

    const DEFAULT_EMPTY_HTML =
      'Run <strong>Moss: Index Workspace</strong> to index your files,<br/>then search here.';

    const prior = vscode.getState();
    if (prior && typeof prior.query === 'string') {
      input.value = prior.query;
    }

    let selectedHitIndex = -1;
    const SEARCH_DEBOUNCE_MS = 320;
    let searchDebounceId = null;

    function persistQuery() {
      vscode.setState({ query: input.value });
    }

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

    function escapeRegExp(s) {
      return s.replace(/[.*+?^\${}()|[\]\\]/g, '\\$&');
    }

    /** Split path into directory (with trailing slash) + basename for display. */
    function splitPath(p) {
      const norm = String(p).replace(/\\\\/g, '/');
      const i = norm.lastIndexOf('/');
      if (i <= 0) {
        return { dir: '', base: norm || '' };
      }
      return { dir: norm.slice(0, i + 1), base: norm.slice(i + 1) };
    }

    /**
     * Wrap query terms (length ≥ 2) in <mark>; split on regex so we never inject HTML from the snippet.
     */
    function highlightSnippet(text, query) {
      const raw = String(text);
      const q = typeof query === 'string' ? query : '';
      const terms = [...new Set(
        q.trim().toLowerCase().split(/\\s+/).filter((t) => t.length >= 2)
      )].sort((a, b) => b.length - a.length);
      if (terms.length === 0) {
        return escapeHtml(raw);
      }
      const pattern = terms.map((t) => escapeRegExp(t)).join('|');
      if (!pattern) {
        return escapeHtml(raw);
      }
      const re = new RegExp('(' + pattern + ')', 'gi');
      const parts = raw.split(re);
      return parts
        .map((part, i) => {
          if (i % 2 === 1) {
            return '<mark class="query-hit">' + escapeHtml(part) + '</mark>';
          }
          return escapeHtml(part);
        })
        .join('');
    }

    function getResultRows() {
      return [...resultList.querySelectorAll('.result-row')];
    }

    function clearResultSelection() {
      selectedHitIndex = -1;
      getResultRows().forEach((el) => {
        el.classList.remove('result-row--selected');
        el.setAttribute('aria-selected', 'false');
        el.tabIndex = -1;
      });
    }

    function applyResultSelection(focusSelected) {
      const focus = focusSelected !== false;
      const rows = getResultRows();
      rows.forEach((el, i) => {
        const on = i === selectedHitIndex;
        el.classList.toggle('result-row--selected', on);
        el.setAttribute('aria-selected', on ? 'true' : 'false');
        el.tabIndex = on ? 0 : -1;
        if (on && focus) {
          el.focus();
          el.scrollIntoView({ block: 'nearest' });
        }
      });
    }

    function openHitIndex(idx) {
      if (!Number.isNaN(idx)) {
        vscode.postMessage({ type: 'openResult', hitIndex: idx });
      }
    }

    function flushLiveQuery() {
      if (searchDebounceId !== null) {
        clearTimeout(searchDebounceId);
        searchDebounceId = null;
      }
      if (input.disabled) return;
      const text = input.value.trim();
      clearError();
      persistQuery();
      vscode.postMessage({ type: 'query', text });
    }

    function scheduleLiveQuery() {
      if (searchDebounceId !== null) clearTimeout(searchDebounceId);
      searchDebounceId = setTimeout(() => {
        searchDebounceId = null;
        flushLiveQuery();
      }, SEARCH_DEBOUNCE_MS);
    }

    if (prior && typeof prior.query === 'string' && prior.query.trim() !== '') {
      scheduleLiveQuery();
    }

    btn.addEventListener('click', () => flushLiveQuery());
    input.addEventListener('input', () => {
      clearResultSelection();
      persistQuery();
      scheduleLiveQuery();
    });
    input.addEventListener('focus', () => {
      clearResultSelection();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        flushLiveQuery();
        return;
      }
      if (e.key === 'ArrowDown' && resultList.style.display !== 'none') {
        const rows = getResultRows();
        if (rows.length === 0) return;
        e.preventDefault();
        selectedHitIndex = 0;
        applyResultSelection();
      }
    });

    resultList.addEventListener('keydown', (e) => {
      const rows = getResultRows();
      if (rows.length === 0) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (selectedHitIndex < rows.length - 1) {
          selectedHitIndex += 1;
          applyResultSelection();
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (selectedHitIndex > 0) {
          selectedHitIndex -= 1;
          applyResultSelection();
        } else {
          clearResultSelection();
          input.focus();
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const idx = parseInt(rows[selectedHitIndex]?.getAttribute('data-hit-index') || '', 10);
        openHitIndex(idx);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        clearResultSelection();
        input.focus();
      }
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg || typeof msg.type !== 'string') return;

      if (msg.type === 'loading') {
        setLoading(!!msg.loading);
        if (msg.loading) {
          clearResultSelection();
          meta.textContent = '';
          if (indexPrep) {
            indexPrep.textContent = '';
            indexPrep.classList.remove('visible');
          }
          resultList.innerHTML = '';
          resultList.style.display = 'none';
          emptyBlock.style.display = 'none';
        }
        return;
      }

      if (msg.type === 'localIndexLoading') {
        if (!indexPrep) return;
        const t = typeof msg.text === 'string' ? msg.text : '';
        if (t) {
          indexPrep.textContent = t;
          indexPrep.classList.add('visible');
        } else {
          indexPrep.textContent = '';
          indexPrep.classList.remove('visible');
        }
        return;
      }

      if (msg.type === 'clearError') {
        clearError();
        return;
      }

      if (msg.type === 'clearResults') {
        clearResultSelection();
        clearError();
        meta.textContent = '';
        if (indexPrep) {
          indexPrep.textContent = '';
          indexPrep.classList.remove('visible');
        }
        resultList.innerHTML = '';
        resultList.style.display = 'none';
        emptyBlock.style.display = 'block';
        emptyState.innerHTML = DEFAULT_EMPTY_HTML;
        return;
      }

      if (msg.type === 'error') {
        clearResultSelection();
        showError(msg.message || 'Search failed.');
        resultList.style.display = 'none';
        resultList.innerHTML = '';
        emptyBlock.style.display = 'block';
        emptyState.innerHTML =
          'Could not complete this search. Fix the issue above, then try again.';
        return;
      }

      if (msg.type === 'results') {
        clearResultSelection();
        const hits = Array.isArray(msg.hits) ? msg.hits : [];
        const queryText = typeof msg.query === 'string' ? msg.query : '';
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
          const rawPath = h.path || '';
          const { dir, base } = splitPath(rawPath);
          const pathHtml =
            (dir
              ? '<span class="result-dir">' + escapeHtml(dir) + '</span>'
              : '') +
            '<span class="result-base">' + escapeHtml(base || rawPath) + '</span>';
          const line = escapeHtml(String(h.lineLabel ?? ''));
          const score = typeof h.score === 'number' ? h.score.toFixed(3) : '';
          const snippet = highlightSnippet(h.snippet || '', queryText);
          return (
            '<li class="result-row" role="option" tabindex="-1" aria-selected="false" data-hit-index="' +
            h.index +
            '">' +
              '<div class="result-path">' + pathHtml + '</div>' +
              '<div class="result-sub">Lines ' + line + (score ? ' · score ' + escapeHtml(score) : '') + '</div>' +
              '<div class="result-snippet">' + snippet + '</div>' +
            '</li>'
          );
        }).join('');

        resultList.querySelectorAll('.result-row').forEach((el) => {
          el.addEventListener('click', () => {
            const idx = parseInt(el.getAttribute('data-hit-index'), 10);
            const rows = getResultRows();
            selectedHitIndex = rows.indexOf(el);
            applyResultSelection(false);
            openHitIndex(idx);
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
