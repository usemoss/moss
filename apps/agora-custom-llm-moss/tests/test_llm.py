"""Mock/doctor tests for the custom-llm middleware. No Agora, no LLM keys."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parents[1] / "server" / "src"
sys.path.insert(0, str(SRC))

import llm  # noqa: E402

PAYLOAD = {
    "model": "mock",
    "stream": True,
    "messages": [{"role": "user", "content": "How long do refunds take?"}],
}

GROUNDING = (
    "Relevant knowledge from Moss:\n\n"
    "[1] Refunds are processed within 3-5 business days once the return is approved."
)


class FakeSession:
    last_time_taken_ms = 3

    async def query_context(self, text: str) -> str:
        return GROUNDING


class BoomSession:
    last_time_taken_ms = None

    async def query_context(self, text: str) -> str:
        raise RuntimeError("timeout")


@pytest.fixture
def hermetic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "load_server_env", lambda *_a, **_k: None)
    for key in (
        "MOSS_PROJECT_ID",
        "MOSS_PROJECT_KEY",
        "MOSS_INDEX_NAME",
        "CUSTOM_LLM_API_KEY",
        "UPSTREAM_LLM_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_env(hermetic_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK", "1")


@pytest.fixture
def moss_ok(hermetic_env, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _open():
        return FakeSession()

    monkeypatch.setattr(llm, "open_moss", _open)


@pytest.fixture
def moss_boom(hermetic_env, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _open():
        return BoomSession()

    monkeypatch.setattr(llm, "open_moss", _open)


def _collect_sse(response) -> str:
    return response.text


def test_mock_ambient_echoes_grounding(mock_env, moss_ok) -> None:
    with TestClient(llm.create_app("ambient")) as client:
        response = client.post("/chat/completions", json=PAYLOAD)
    assert response.status_code == 200
    body = _collect_sse(response)
    assert "data: [DONE]" in body
    assert "3-5" in body
    assert "tool_calls" not in body


def test_mock_tool_echoes_grounding_and_hides_tool(mock_env, moss_ok) -> None:
    with TestClient(llm.create_app("tool")) as client:
        response = client.post("/chat/completions", json=PAYLOAD)
    assert response.status_code == 200
    body = _collect_sse(response)
    assert "data: [DONE]" in body
    assert "3-5" in body
    # Agora must only see the spoken answer, never the tool schema.
    assert "search_knowledge_base" not in body


def test_bearer_missing_rejected_when_not_mock(monkeypatch: pytest.MonkeyPatch, moss_ok) -> None:
    monkeypatch.setenv("MOCK", "0")
    monkeypatch.setenv("CUSTOM_LLM_API_KEY", "secret")
    with TestClient(llm.create_app("ambient")) as client:
        denied = client.post("/chat/completions", json=PAYLOAD)
        assert denied.status_code == 401
        ok = client.post(
            "/chat/completions",
            json=PAYLOAD,
            headers={"Authorization": "Bearer secret"},
        )
        # Without MOCK the handler tries the upstream LLM; we only assert Bearer.
        assert ok.status_code != 401


def test_unset_key_rejects_any_bearer(monkeypatch: pytest.MonkeyPatch, moss_ok) -> None:
    monkeypatch.setenv("MOCK", "0")
    with TestClient(llm.create_app("ambient")) as client:
        denied = client.post(
            "/chat/completions",
            json=PAYLOAD,
            headers={"Authorization": "Bearer anything-at-all"},
        )
    assert denied.status_code == 401


def test_search_query_non_object_falls_back_to_user_text() -> None:
    fallback = "How long do refunds take?"
    assert llm.search_query('{"query": "refunds"}', fallback) == "refunds"
    assert llm.search_query('["refunds"]', fallback) == fallback
    assert llm.search_query("42", fallback) == fallback
    assert llm.search_query("not-json", fallback) == fallback
    assert llm.search_query('{"query": ""}', fallback) == fallback


def test_moss_error_fail_open_still_streams(mock_env, moss_boom) -> None:
    with TestClient(llm.create_app("ambient")) as client:
        response = client.post("/chat/completions", json=PAYLOAD)
    assert response.status_code == 200
    assert "data: [DONE]" in response.text


def test_non_stream_rejected(mock_env, moss_ok) -> None:
    with TestClient(llm.create_app("ambient")) as client:
        response = client.post(
            "/chat/completions",
            json={**PAYLOAD, "stream": False},
        )
    assert response.status_code == 400


def test_server_mounts_open_moss_on_first_request(mock_env, moss_ok) -> None:
    import server as server_mod

    with TestClient(server_mod.app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        ambient = client.post("/llm/chat/completions", json=PAYLOAD)
        tool = client.post("/llm-tools/chat/completions", json=PAYLOAD)
    assert ambient.status_code == 200 and "3-5" in ambient.text
    assert tool.status_code == 200 and "3-5" in tool.text
    assert "search_knowledge_base" not in tool.text


def test_load_server_env_reads_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("CUSTOM_LLM_API_KEY=from-dotenv-file\n")
    monkeypatch.delenv("CUSTOM_LLM_API_KEY", raising=False)
    llm.load_server_env(tmp_path)
    assert os.environ.get("CUSTOM_LLM_API_KEY") == "from-dotenv-file"


def test_last_user_text_from_list_content() -> None:
    msg = llm.UserMessage(role="user", content=[{"type": "text", "text": "hello"}])
    assert llm.last_user_text([msg]) == "hello"


def test_doctor_entrypoint(monkeypatch: pytest.MonkeyPatch, moss_ok, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MOCK", "1")
    llm.run_doctor()
    out = capsys.readouterr().out
    assert "doctor: ok" in out


def test_doctor_unset_key_survives_dotenv_reload(
    monkeypatch: pytest.MonkeyPatch, moss_ok, capsys: pytest.CaptureFixture[str]
) -> None:
    def _load(_server_dir=None) -> None:
        os.environ["CUSTOM_LLM_API_KEY"] = "anything"

    monkeypatch.setattr(llm, "load_server_env", _load)
    llm.run_doctor()
    out = capsys.readouterr().out
    assert "rejected any token while CUSTOM_LLM_API_KEY is unset" in out
    assert "doctor: ok" in out


def test_doctor_restores_preset_env(
    monkeypatch: pytest.MonkeyPatch, moss_ok
) -> None:
    monkeypatch.setenv("MOCK", "preset")
    monkeypatch.setenv("CUSTOM_LLM_API_KEY", "preset-key")
    llm.run_doctor()
    assert os.environ["MOCK"] == "preset"
    assert os.environ["CUSTOM_LLM_API_KEY"] == "preset-key"


def test_doctor_restores_absent_env(
    monkeypatch: pytest.MonkeyPatch, moss_ok
) -> None:
    monkeypatch.delenv("MOCK", raising=False)
    monkeypatch.delenv("CUSTOM_LLM_API_KEY", raising=False)
    llm.run_doctor()
    assert "MOCK" not in os.environ
    assert "CUSTOM_LLM_API_KEY" not in os.environ
