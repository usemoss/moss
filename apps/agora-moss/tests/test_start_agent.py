"""Tests for start_agent.py."""

import sys
from pathlib import Path

import pytest

# Make the top-level demo modules importable when pytest runs from the package dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestBuildJoinBody:
    def test_includes_mcp_servers_with_allowed_tools(self):
        from start_agent import build_join_body

        body = build_join_body(
            channel="ch1",
            agent_rtc_uid=123,
            agent_rtc_token="token-xyz",
            llm_url="https://llm.example/chat",
            llm_api_key="llmkey",
            mcp_public_url="https://mcp.example/mcp",
            mcp_auth_header="Bearer abc",
            deepgram_key="dg",
            cartesia_key="ct",
            cartesia_voice_id="voice-1",
        )
        llm = body["properties"]["llm"]
        assert llm["vendor"] == "custom"
        assert llm["url"] == "https://llm.example/chat"
        assert llm["api_key"] == "llmkey"

        assert len(llm["mcp_servers"]) == 1
        mcp = llm["mcp_servers"][0]
        assert mcp["name"] == "moss"
        assert mcp["endpoint"] == "https://mcp.example/mcp"
        assert mcp["transport"] == "streamable_http"
        assert mcp["allowed_tools"] == ["search_knowledge_base"]
        assert mcp["headers"] == {"Authorization": "Bearer abc"}

    def test_enable_tools_is_true(self):
        from start_agent import build_join_body

        body = build_join_body(
            channel="c",
            agent_rtc_uid=1,
            agent_rtc_token="t",
            llm_url="x",
            llm_api_key="y",
            mcp_public_url="z",
            mcp_auth_header=None,
            deepgram_key="dg",
            cartesia_key="ct",
            cartesia_voice_id="v",
        )
        assert body["properties"]["advanced_features"]["enable_tools"] is True

    def test_includes_asr_tts_and_turn_detection(self):
        from start_agent import build_join_body

        body = build_join_body(
            channel="c",
            agent_rtc_uid=1,
            agent_rtc_token="t",
            llm_url="x",
            llm_api_key="y",
            mcp_public_url="z",
            mcp_auth_header=None,
            deepgram_key="dgk",
            cartesia_key="ctk",
            cartesia_voice_id="vid",
        )
        props = body["properties"]
        assert props["asr"]["vendor"] == "deepgram"
        assert props["asr"]["params"]["key"] == "dgk"
        assert props["asr"]["params"]["model"] == "nova-3"

        assert props["tts"]["vendor"] == "cartesia"
        assert props["tts"]["params"]["api_key"] == "ctk"
        assert props["tts"]["params"]["voice"] == {"mode": "id", "id": "vid"}

        assert props["turn_detection"] == {"mode": "default"}

    def test_omits_headers_when_no_auth_header_supplied(self):
        from start_agent import build_join_body

        body = build_join_body(
            channel="c",
            agent_rtc_uid=1,
            agent_rtc_token="t",
            llm_url="x",
            llm_api_key="y",
            mcp_public_url="z",
            mcp_auth_header=None,
            deepgram_key="dg",
            cartesia_key="ct",
            cartesia_voice_id="v",
        )
        mcp = body["properties"]["llm"]["mcp_servers"][0]
        assert "headers" not in mcp


class TestMcpServerName:
    def test_mcp_server_name_is_alphanumeric_and_short(self):
        # Agora rule: name <= 48 chars, alphanumeric only.
        from start_agent import MCP_SERVER_NAME

        assert MCP_SERVER_NAME.isalnum()
        assert 1 <= len(MCP_SERVER_NAME) <= 48

    def test_build_join_body_rejects_bad_name(self, monkeypatch):
        import start_agent

        monkeypatch.setattr(start_agent, "MCP_SERVER_NAME", "has-hyphen")
        with pytest.raises(ValueError, match="alphanumeric"):
            start_agent.build_join_body(
                channel="c",
                agent_rtc_uid=1,
                agent_rtc_token="t",
                llm_url="x",
                llm_api_key="y",
                mcp_public_url="z",
                mcp_auth_header=None,
                deepgram_key="dg",
                cartesia_key="ct",
                cartesia_voice_id="v",
            )
