"""moss playground — local web UI for querying Moss indexes interactively.

Starts a local HTTP server that serves a browser-based playground. The UI
loads ``@moss-dev/moss-web`` (the WASM browser SDK) via an import map from the
unpkg CDN and executes index loading and queries entirely in the browser.

The server only serves the static UI and, when credentials are available,
injects them through a token-protected ``/api/config`` endpoint so the WASM
client can talk to the Moss cloud directly. When no credentials are configured,
the UI falls back to a manual connection form.
"""

from __future__ import annotations

import json
import secrets
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.markup import escape as rich_escape

from ..config import resolve_credentials

console = Console()
HERE = Path(__file__).resolve().parent.parent

PLAYGROUND_HTML = HERE / "playground" / "index.html"


class DaemonThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer whose per-request threads are daemons.

    By default ThreadingHTTPServer's request threads are non-daemon, so
    server_close() blocks waiting for any in-flight request thread to
    finish. Daemonizing request threads lets process exit proceed without
    waiting on them.
    """

    daemon_threads = True


class PlaygroundHandler(SimpleHTTPRequestHandler):
    """HTTP handler — serves the playground UI and injects credentials into the
    browser when the server has them, so the WASM client runs entirely in the
    browser."""

    _token: str = ""
    _server_host: str = ""
    _project_id: str | None = None
    _project_key: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE / "playground"), **kwargs)

    def _check_api_request(self) -> bool:
        token = self.headers.get("X-Moss-Token")
        if token is None or not secrets.compare_digest(token, self._token):
            self._send_json(403, {"error": "Forbidden: invalid or missing token"})
            return False
        host = self.headers.get("Host", "")
        allowed_hosts = {self._server_host, self._server_host.replace("127.0.0.1", "localhost")}
        if host and host not in allowed_hosts:
            self._send_json(403, {"error": "Forbidden: invalid Host header"})
            return False
        origin = self.headers.get("Origin", "")
        allowed_origins = {f"http://{h}" for h in allowed_hosts}
        if origin and origin not in allowed_origins:
            self._send_json(403, {"error": "Forbidden: invalid Origin"})
            return False
        return True

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_index()
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        elif path == "/api/config":
            if not self._check_api_request():
                return
            self._handle_get_config()
        else:
            super().do_GET()

    def _serve_index(self) -> None:
        if not PLAYGROUND_HTML.exists():
            self._send_json(500, {"error": "Playground HTML not found"})
            return
        html = PLAYGROUND_HTML.read_text(encoding="utf-8")
        self._send_html(html)

    def _handle_get_config(self) -> None:
        self._send_json(
            200,
            {
                "projectId": self._project_id,
                "projectKey": self._project_key,
            },
        )

    def log_message(self, format, *args):
        safe = [rich_escape(str(a)) for a in args]
        if len(safe) >= 3:
            console.print(f"  [dim]{safe[0]} {safe[1]} {safe[2]}[/dim]")
        elif len(safe) >= 2:
            console.print(f"  [dim]{safe[0]} {safe[1]}[/dim]")
        elif len(safe) >= 1:
            console.print(f"  [dim]{safe[0]}[/dim]")


def _create_server(
    handler: type,
    start: int = 8765,
    max_attempts: int = 20,
) -> tuple[DaemonThreadingHTTPServer, int]:
    """Construct the HTTP server on the first free port in the candidate range.

    Binding happens inside ``DaemonThreadingHTTPServer``, so a port that is
    probed free and then taken by another process is retried instead of
    crashing the command (unlike a separate check-then-bind probe).
    """
    last_error: OSError | None = None
    for port in range(start, start + max_attempts):
        try:
            return DaemonThreadingHTTPServer(("127.0.0.1", port), handler), port
        except OSError as e:
            last_error = e
            continue
    raise RuntimeError(
        f"Could not find a free port in range {start}-{start + max_attempts}"
    ) from last_error


def playground_command(
    ctx: typer.Context,
    port: int = typer.Option(0, "--port", "-p", help="Port for the HTTP server (0 = auto)"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Credential profile name",
    ),
    no_open: bool = typer.Option(
        False, "--no-open", help="Do not open the browser automatically",
    ),
) -> None:
    """Start the Moss Playground — a browser-based UI for interactive search.

    Launches a browser-based playground that loads the Moss WASM SDK
    (@moss-dev/moss-web) and runs index loading and queries entirely in the
    browser. Credentials from CLI flags, env vars, or a config profile are
    injected through a token-protected endpoint; without them the UI shows a
    manual connection form.
    """
    if profile:
        ctx.obj["profile"] = profile

    # Resolve credentials if available — the playground still works without
    # them by asking the user to connect manually in the browser.
    try:
        pid, pkey = resolve_credentials(
            ctx.obj.get("project_id"), ctx.obj.get("project_key"), ctx.obj.get("profile")
        )
    except typer.BadParameter:
        pid, pkey = None, None

    # Start server
    if port:
        server = DaemonThreadingHTTPServer(("127.0.0.1", port), PlaygroundHandler)
        final_port = port
    else:
        server, final_port = _create_server(PlaygroundHandler)

    PlaygroundHandler._token = secrets.token_urlsafe(32)
    PlaygroundHandler._server_host = f"127.0.0.1:{final_port}"
    PlaygroundHandler._project_id = pid
    PlaygroundHandler._project_key = pkey

    url = f"http://127.0.0.1:{final_port}"
    frag_url = f"{url}/#{PlaygroundHandler._token}"

    console.print()
    console.print("  [bold]Moss Playground[/bold]")
    console.print(f"  [dim]Server:[/dim]  [cyan]{frag_url}[/cyan]")
    if pid:
        console.print(f"  [dim]Project:[/dim] {pid[:8]}...")
    else:
        console.print(
            "  [yellow]No credentials found — enter them in the browser connection form.[/yellow]"
        )
    console.print("  [dim]Stop:[/dim]    Ctrl+C")
    console.print()

    opened = False
    if not no_open:
        opened = webbrowser.open(frag_url)
    if not opened:
        console.print("  [yellow]Open this URL in your browser:[/yellow]")
        console.print(f"  [cyan]{frag_url}[/cyan]")
        console.print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
    finally:
        server.server_close()
