from moss_cli.commands.playground import PLAYGROUND_HTML, PlaygroundHandler


def _make_config_handler(monkeypatch, pid=None, pkey=None):
    handler = PlaygroundHandler.__new__(PlaygroundHandler)
    captured = {}

    def fake_send_json(status, data):
        captured["status"] = status
        captured["data"] = data

    monkeypatch.setattr(handler, "_send_json", fake_send_json)
    monkeypatch.setattr(PlaygroundHandler, "_project_id", pid)
    monkeypatch.setattr(PlaygroundHandler, "_project_key", pkey)
    return handler, captured


def _make_token_handler(monkeypatch):
    handler = PlaygroundHandler.__new__(PlaygroundHandler)
    captured = {}

    def fake_send_json(status, data):
        captured["status"] = status
        captured["data"] = data

    monkeypatch.setattr(handler, "_send_json", fake_send_json)
    monkeypatch.setattr(PlaygroundHandler, "_token", "secret-token")
    monkeypatch.setattr(PlaygroundHandler, "_server_host", "127.0.0.1:8765")
    return handler, captured


def _auth_headers(**extra):
    headers = {
        "X-Moss-Token": "secret-token",
        "Host": "127.0.0.1:8765",
        "Origin": "http://127.0.0.1:8765",
    }
    headers.update(extra)
    return headers


def test_playground_html_asset_exists():
    assert PLAYGROUND_HTML.exists(), (
        f"Playground HTML not found at {PLAYGROUND_HTML}. "
        "Check that the asset is included in the package data."
    )


def test_html_includes_wasm_importmap():
    html = PLAYGROUND_HTML.read_text(encoding="utf-8")
    assert '<script type="importmap">' in html
    assert "https://unpkg.com/@moss-dev/moss-web@" in html
    assert "https://unpkg.com/@moss-dev/moss-wasm@" in html
    assert "https://unpkg.com/onnxruntime-web@" in html


def test_html_loads_moss_web_in_browser():
    html = PLAYGROUND_HTML.read_text(encoding="utf-8")
    assert "import('@moss-dev/moss-web')" in html
    assert "MossClient.create" in html


def test_html_has_manual_connection_form():
    html = PLAYGROUND_HTML.read_text(encoding="utf-8")
    assert 'id="connect-form"' in html
    assert 'id="pid-input"' in html
    assert 'id="pkey-input"' in html


def test_html_queries_in_browser_not_via_server():
    html = PLAYGROUND_HTML.read_text(encoding="utf-8")
    assert "client.query(" in html
    assert "client.loadIndex(" in html
    assert "/api/query" not in html
    assert "/api/load-index" not in html


def test_html_renders_metadata_safely():
    html = PLAYGROUND_HTML.read_text(encoding="utf-8")
    assert "result-metadata" in html
    assert "JSON.stringify(doc.metadata, null, 2)" in html
    assert "textContent" in html


def test_config_returns_injected_credentials(monkeypatch):
    handler, captured = _make_config_handler(monkeypatch, pid="proj-1", pkey="key-1")
    handler._handle_get_config()
    assert captured["status"] == 200
    assert captured["data"] == {"projectId": "proj-1", "projectKey": "key-1"}


def test_config_returns_nulls_without_credentials(monkeypatch):
    handler, captured = _make_config_handler(monkeypatch)
    handler._handle_get_config()
    assert captured["status"] == 200
    assert captured["data"] == {"projectId": None, "projectKey": None}


def test_config_requires_token(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.path = "/api/config"
    handler.headers = {"Host": "127.0.0.1:8765"}
    handler.do_GET()
    assert captured["status"] == 403


def test_config_allows_valid_token(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.path = "/api/config"
    handler.headers = _auth_headers()
    handler.do_GET()
    assert captured["status"] == 200
    assert captured["data"] == {"projectId": None, "projectKey": None}


def test_check_api_request_missing_token(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.headers = {"Host": "127.0.0.1:8765"}
    assert handler._check_api_request() is False
    assert captured["status"] == 403


def test_check_api_request_wrong_token(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.headers = {"X-Moss-Token": "wrong", "Host": "127.0.0.1:8765"}
    assert handler._check_api_request() is False
    assert captured["status"] == 403


def test_check_api_request_foreign_host(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.headers = {"X-Moss-Token": "secret-token", "Host": "evil.example.com"}
    assert handler._check_api_request() is False
    assert captured["status"] == 403


def test_check_api_request_foreign_origin(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.headers = {
        "X-Moss-Token": "secret-token",
        "Host": "127.0.0.1:8765",
        "Origin": "http://evil.example.com",
    }
    assert handler._check_api_request() is False
    assert captured["status"] == 403


def test_check_api_request_allows_valid_request(monkeypatch):
    handler, captured = _make_token_handler(monkeypatch)
    handler.headers = {
        "X-Moss-Token": "secret-token",
        "Host": "localhost:8765",
        "Origin": "http://localhost:8765",
    }
    assert handler._check_api_request() is True
    assert "status" not in captured
