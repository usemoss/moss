import * as vscode from "vscode";

export class MossSearchViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewId = "moss.searchView";

  private _view?: vscode.WebviewView;

  constructor(private readonly _extensionUri: vscode.Uri) {}

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

    webviewView.webview.onDidReceiveMessage((message) => {
      switch (message.type) {
        case "query":
          void vscode.window.showInformationMessage(
            `Moss search for "${message.text}" — query execution not yet implemented.`
          );
          break;
        case "openResult":
          break;
      }
    });
  }

  private _getHtml(webview: vscode.Webview): string {
    const nonce = getNonce();

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style nonce="${nonce}">
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      color: var(--vscode-foreground);
      padding: 12px 14px;
    }
    .search-box {
      display: flex;
      gap: 6px;
      margin-bottom: 12px;
    }
    .search-box input {
      flex: 1;
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
    .search-box button {
      padding: 5px 12px;
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 2px;
      cursor: pointer;
      font-size: inherit;
      font-family: inherit;
    }
    .search-box button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .empty-state {
      color: var(--vscode-descriptionForeground);
      font-size: 0.9em;
      line-height: 1.6;
      text-align: center;
      margin-top: 24px;
    }
  </style>
</head>
<body>
  <div class="search-box">
    <input type="text" id="query" placeholder="Search your codebase…" />
    <button id="searchBtn">Search</button>
  </div>
  <div id="results">
    <p class="empty-state">
      Run <strong>Moss: Index Workspace</strong> to index your files,<br/>
      then search here.
    </p>
  </div>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const input = document.getElementById('query');
    const btn = document.getElementById('searchBtn');

    function submitQuery() {
      const text = input.value.trim();
      if (text) {
        vscode.postMessage({ type: 'query', text });
      }
    }

    btn.addEventListener('click', submitQuery);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submitQuery();
    });
  </script>
</body>
</html>`;
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
