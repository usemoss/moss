import * as vscode from "vscode";
import type { MossSettingsSnapshot } from "../moss/config";
import type { IndexStatus } from "../indexer/indexer";
import type { SearchHit } from "../search/search";

export type SidebarCallbacks = {
  onQuery: (query: string) => Promise<SearchHit[]>;
  onOpen: (hit: SearchHit) => Promise<void>;
  onCreateIndex: () => Promise<void>;
  onSyncCloud: () => Promise<void>;
  onGetSettings: () => Promise<MossSettingsSnapshot>;
  onSaveSettings: (settings: {
    projectId: string;
    projectKey?: string;
    cloudSync: boolean;
  }) => Promise<{ ok: boolean; message?: string }>;
};

export type CloudSyncUiState = "idle" | "syncing" | "success" | "error";

export class MossSearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "moss.searchView";

  private view?: vscode.WebviewView;
  private status: IndexStatus = { state: "unindexed" };

  constructor(
    private readonly extensionUri: vscode.Uri,
    private readonly callbacks: SidebarCallbacks,
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken,
  ): void {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, "media")],
    };
    webviewView.webview.html = this.getHtml(webviewView.webview);
    this.postStatus(this.status);
    void this.callbacks.onGetSettings().then((settings) => this.postSettings(settings));

    webviewView.webview.onDidReceiveMessage(async (message) => {
      if (!message || typeof message !== "object") {
        return;
      }
      try {
        if (message.type === "query" && typeof message.text === "string") {
          if (this.status.state !== "ready") {
            this.postResults([]);
            return;
          }
          const hits = await this.callbacks.onQuery(message.text);
          this.postResults(hits);
        }
        if (message.type === "createIndex") {
          await this.callbacks.onCreateIndex();
        }
        if (message.type === "syncCloud") {
          await this.callbacks.onSyncCloud();
        }
        if (message.type === "getSettings") {
          const settings = await this.callbacks.onGetSettings();
          this.postSettings(settings);
        }
        if (message.type === "saveSettings" && message.settings) {
          const result = await this.callbacks.onSaveSettings(message.settings);
          this.view?.webview.postMessage({ type: "settingsSaved", ...result });
          if (result.ok) {
            const settings = await this.callbacks.onGetSettings();
            this.postSettings(settings);
          }
        }
        if (message.type === "openExternal" && typeof message.url === "string") {
          await vscode.env.openExternal(vscode.Uri.parse(message.url));
        }
        if (message.type === "open" && message.hit) {
          await this.callbacks.onOpen(message.hit as SearchHit);
        }
      } catch (err) {
        const error = err instanceof Error ? err.message : String(err);
        this.postError(error);
      }
    });
  }

  setStatus(status: IndexStatus): void {
    this.status = status;
    this.postStatus(status);
  }

  setCloudSyncState(state: CloudSyncUiState, message?: string): void {
    this.view?.webview.postMessage({ type: "cloudSync", state, message });
  }

  postSettings(settings: MossSettingsSnapshot): void {
    this.view?.webview.postMessage({ type: "settings", settings });
  }

  openSettings(): void {
    this.view?.webview.postMessage({ type: "openSettings" });
  }

  private postStatus(status: IndexStatus): void {
    this.view?.webview.postMessage({ type: "status", status });
  }

  private postResults(hits: SearchHit[]): void {
    this.view?.webview.postMessage({ type: "results", hits });
  }

  private postError(error: string): void {
    this.view?.webview.postMessage({ type: "error", error });
  }

  private getHtml(webview: vscode.Webview): string {
    const cssUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "sidebar.css"),
    );
    const wordmarkLightUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "moss_wordmark_light.png"),
    );
    const wordmarkDarkUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "moss_wordmark_dark.png"),
    );
    const avatarUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "moss_avatar_core.png"),
    );
    const nonce = getNonce();

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; img-src ${webview.cspSource} data:; script-src 'nonce-${nonce}';" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="${cssUri}" />
  <title>Moss Search</title>
</head>
<body>
  <div class="container">
    <header class="brand-header">
      <div class="brand-title">
        <img class="brand-wordmark brand-wordmark-dark" src="${wordmarkDarkUri}" alt="Moss" />
        <img class="brand-wordmark brand-wordmark-light" src="${wordmarkLightUri}" alt="Moss" />
      </div>
      <button id="settings-toggle" type="button" class="icon-btn" title="Settings" aria-label="Moss settings">
        <svg class="gear-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
          <path fill="currentColor" d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492zM5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0z"/>
          <path fill="currentColor" d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52l-.094-.319zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115l.094-.319z"/>
        </svg>
      </button>
    </header>
    <div id="settings-panel" class="settings-panel" hidden>
      <div class="settings-header">
        <span class="settings-title">Settings</span>
      </div>
      <label class="field-label" for="project-id">Project ID</label>
      <input id="project-id" type="text" class="field-input" placeholder="MOSS_PROJECT_ID" autocomplete="off" />
      <label class="field-label" for="project-key">Project Key</label>
      <input id="project-key" type="password" class="field-input" placeholder="Leave blank to keep saved key" autocomplete="off" />
      <p id="credentials-hint" class="field-hint">Get credentials at <a href="#" id="moss-link" class="field-link">moss.dev</a></p>
      <label class="toggle-row">
        <input id="cloud-sync" type="checkbox" />
        <span>Sync index to Moss Cloud</span>
      </label>
      <p class="field-hint">When enabled, indexes upload after indexing and restore from cloud on new machines.</p>
      <button id="save-settings" type="button" class="primary-btn settings-save">Save</button>
      <p id="settings-status" class="settings-status" hidden></p>
    </div>
    <p class="brand-tagline">Semantic code search</p>
    <div id="index-panel" class="index-panel">
      <p class="index-hint">Index this workspace to enable semantic search.</p>
      <button id="create-index" type="button" class="primary-btn">Create Index</button>
    </div>
    <div class="search-row">
      <input id="query" type="search" placeholder="Semantic search…" autocomplete="off" disabled />
    </div>
    <div id="actions-row" class="actions-row" hidden>
      <button id="sync-cloud" type="button" class="secondary-btn">Sync to Cloud</button>
    </div>
    <div class="status-row">
      <img id="status-avatar" class="status-avatar" src="${avatarUri}" alt="" />
      <div id="status">Not indexed</div>
    </div>
    <ul id="results"></ul>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const input = document.getElementById('query');
    const statusEl = document.getElementById('status');
    const statusAvatar = document.getElementById('status-avatar');
    const resultsEl = document.getElementById('results');
    const indexPanel = document.getElementById('index-panel');
    const createBtn = document.getElementById('create-index');
    const actionsRow = document.getElementById('actions-row');
    const syncBtn = document.getElementById('sync-cloud');
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsPanel = document.getElementById('settings-panel');
    const projectIdInput = document.getElementById('project-id');
    const projectKeyInput = document.getElementById('project-key');
    const cloudSyncInput = document.getElementById('cloud-sync');
    const saveSettingsBtn = document.getElementById('save-settings');
    const settingsStatus = document.getElementById('settings-status');
    const mossLink = document.getElementById('moss-link');
    let timer;
    let syncResetTimer;
    let settingsOpen = false;

    function formatStatus(status) {
      if (!status) return 'Not indexed';
      if (status.state === 'indexing') {
        return 'Indexing ' + status.processed + '/' + status.total + '…';
      }
      if (status.state === 'ready') {
        return 'Ready — ' + status.files + ' files, ' + status.chunks + ' chunks';
      }
      if (status.state === 'error') {
        return 'Error: ' + status.message;
      }
      if (status.state === 'unindexed') {
        return 'Not indexed — click Create Index';
      }
      return 'Not indexed';
    }

    function setSyncButton(state, message) {
      if (!syncBtn) return;
      clearTimeout(syncResetTimer);
      if (state === 'syncing') {
        syncBtn.disabled = true;
        syncBtn.textContent = 'Syncing…';
        return;
      }
      if (state === 'success') {
        syncBtn.disabled = false;
        syncBtn.textContent = 'Synced to Cloud';
        syncResetTimer = setTimeout(() => {
          syncBtn.textContent = 'Sync to Cloud';
        }, 2500);
        return;
      }
      if (state === 'error') {
        syncBtn.disabled = false;
        syncBtn.textContent = 'Sync failed — retry';
        if (message) {
          statusEl.textContent = message;
          statusAvatar.classList.remove('visible');
        }
        return;
      }
      syncBtn.disabled = false;
      syncBtn.textContent = 'Sync to Cloud';
    }

    function applyStatus(status) {
      const ready = status && status.state === 'ready';
      const indexing = status && status.state === 'indexing';
      input.disabled = !ready;
      indexPanel.style.display = ready || indexing ? 'none' : 'block';
      if (actionsRow) {
        actionsRow.hidden = !ready;
      }
      createBtn.disabled = indexing;
      createBtn.textContent = indexing ? 'Indexing…' : 'Create Index';
      statusEl.textContent = formatStatus(status);
      statusAvatar.classList.toggle('visible', !!ready);
      if (!ready && !input.value.trim()) {
        renderHits([]);
      }
      if (!ready) {
        setSyncButton('idle');
      }
    }

    function renderHits(hits) {
      resultsEl.innerHTML = '';
      if (input.disabled) {
        const empty = document.createElement('li');
        empty.className = 'empty';
        empty.textContent = 'Create an index first, then search your codebase.';
        resultsEl.appendChild(empty);
        return;
      }
      if (!hits || !hits.length) {
        const empty = document.createElement('li');
        empty.className = 'empty';
        empty.textContent = input.value.trim() ? 'No results' : 'Type to search your codebase';
        resultsEl.appendChild(empty);
        return;
      }
      for (const hit of hits) {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.className = 'result';
        btn.type = 'button';
        const header = document.createElement('div');
        header.className = 'result-header';
        const path = document.createElement('span');
        path.className = 'path';
        path.textContent = hit.filePath + ':' + hit.startLine;
        const score = document.createElement('span');
        score.className = 'score';
        score.textContent = (hit.score ?? 0).toFixed(3);
        header.appendChild(path);
        header.appendChild(score);
        const preview = document.createElement('div');
        preview.className = 'preview';
        preview.textContent = (hit.text || '').trim();
        btn.appendChild(header);
        btn.appendChild(preview);
        btn.addEventListener('click', () => {
          vscode.postMessage({ type: 'open', hit });
        });
        li.appendChild(btn);
        resultsEl.appendChild(li);
      }
    }

    function setSettingsOpen(open) {
      settingsOpen = open;
      if (settingsPanel) {
        settingsPanel.hidden = !open;
      }
      if (settingsToggle) {
        settingsToggle.classList.toggle('active', open);
        settingsToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      }
      if (open) {
        vscode.postMessage({ type: 'getSettings' });
      }
    }

    function applySettings(settings) {
      if (!settings) return;
      if (projectIdInput) {
        projectIdInput.value = settings.projectId || '';
      }
      if (projectKeyInput) {
        projectKeyInput.value = '';
        projectKeyInput.placeholder = settings.hasProjectKey
          ? 'Saved — enter new key to replace'
          : 'MOSS_PROJECT_KEY';
      }
      if (cloudSyncInput) {
        cloudSyncInput.checked = !!settings.cloudSync;
      }
      if (settingsStatus) {
        settingsStatus.hidden = true;
      }
    }

    function showSettingsStatus(text, isError) {
      if (!settingsStatus) return;
      settingsStatus.hidden = false;
      settingsStatus.textContent = text;
      settingsStatus.classList.toggle('error', !!isError);
    }

    settingsToggle.addEventListener('click', () => {
      setSettingsOpen(!settingsOpen);
    });

    saveSettingsBtn.addEventListener('click', () => {
      saveSettingsBtn.disabled = true;
      showSettingsStatus('Saving…', false);
      vscode.postMessage({
        type: 'saveSettings',
        settings: {
          projectId: projectIdInput ? projectIdInput.value.trim() : '',
          projectKey: projectKeyInput ? projectKeyInput.value : '',
          cloudSync: cloudSyncInput ? cloudSyncInput.checked : true,
        },
      });
    });

    if (mossLink) {
      mossLink.addEventListener('click', (e) => {
        e.preventDefault();
        vscode.postMessage({ type: 'openExternal', url: 'https://moss.dev' });
      });
    }

    createBtn.addEventListener('click', () => {
      vscode.postMessage({ type: 'createIndex' });
    });

    syncBtn.addEventListener('click', () => {
      setSyncButton('syncing');
      vscode.postMessage({ type: 'syncCloud' });
    });

    input.addEventListener('input', () => {
      if (input.disabled) return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        vscode.postMessage({ type: 'query', text: input.value });
      }, 250);
    });

    window.addEventListener('message', (event) => {
      const msg = event.data;
      if (!msg) return;
      if (msg.type === 'status') {
        applyStatus(msg.status);
      }
      if (msg.type === 'results') {
        renderHits(msg.hits || []);
      }
      if (msg.type === 'error') {
        statusEl.textContent = 'Search error: ' + msg.error;
        statusAvatar.classList.remove('visible');
      }
      if (msg.type === 'cloudSync') {
        setSyncButton(msg.state || 'idle', msg.message);
      }
      if (msg.type === 'settings') {
        applySettings(msg.settings);
      }
      if (msg.type === 'openSettings') {
        setSettingsOpen(true);
      }
      if (msg.type === 'settingsSaved') {
        if (saveSettingsBtn) saveSettingsBtn.disabled = false;
        if (msg.ok) {
          showSettingsStatus(msg.message || 'Settings saved.', false);
          if (projectKeyInput) projectKeyInput.value = '';
        } else {
          showSettingsStatus(msg.message || 'Could not save settings.', true);
        }
      }
    });

    applyStatus({ state: 'unindexed' });
    renderHits([]);
  </script>
</body>
</html>`;
  }
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let text = "";
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}
