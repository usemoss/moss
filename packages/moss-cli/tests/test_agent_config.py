"""Tests for moss agent-config command."""

from __future__ import annotations

import os
import types
from unittest.mock import AsyncMock, Mock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_index, parse_json


class TestAgentConfigDefaults:
    def test_default_framework_is_mcp(self, runner: CliRunner) -> None:
        """Default framework should be mcp."""
        with patch("moss_cli.commands.agent_config._resolve_credential_soft", return_value=None), \
             patch("moss_cli.commands.agent_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "agent-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["framework"] == "mcp"

    def test_placeholder_project_id_when_no_credentials(self, runner: CliRunner) -> None:
        """Should use placeholder when no credentials available."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("MOSS_")}
        with patch("moss_cli.commands.agent_config.load_config", return_value={}), \
             patch.dict("os.environ", clean_env, clear=True):
            result = runner.invoke(
                app,
                ["--json", "agent-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["project_id"] == "<your-project-id>"

    def test_project_id_from_flags(self, runner: CliRunner) -> None:
        """Should use project ID from CLI flags."""
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "my-pid",
                    "--project-key", "my-pkey",
                    "agent-config",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["project_id"] == "my-pid"


class TestAgentConfigFrameworks:
    def test_vercel_ai_sdk_framework(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--framework", "vercel-ai-sdk",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["framework"] == "vercel-ai-sdk"
        assert "createMossTools" in data["quickstart"]

    def test_langchain_framework(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--framework", "langchain",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["framework"] == "langchain"
        assert "MossSearchTool" in data["quickstart"]

    def test_openai_agents_framework(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--framework", "openai-agents",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["framework"] == "openai-agents"
        assert "moss_search_tool" in data["quickstart"]

    def test_rest_framework(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--framework", "rest",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["framework"] == "rest"
        assert "curl" in data["quickstart"]

    def test_unsupported_framework_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "agent-config", "--framework", "django"],
        )

        assert result.exit_code != 0


class TestAgentConfigIndexes:
    def test_indexes_fetched_when_credentials_available(self, runner: CliRunner) -> None:
        """Should fetch and include indexes when credentials are available."""
        fake_indexes = [
            {"name": "docs", "status": "Ready", "doc_count": 100, "model": "moss-minilm"},
            {"name": "code", "status": "Ready", "doc_count": 50, "model": "moss-minilm"},
        ]
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=fake_indexes):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data["indexes"]) == 2
        assert data["indexes"][0]["name"] == "docs"

    def test_focus_index_filters(self, runner: CliRunner) -> None:
        """--index flag should filter to the specified index."""
        fake_indexes = [
            {"name": "docs", "status": "Ready", "doc_count": 100, "model": "moss-minilm"},
            {"name": "code", "status": "Ready", "doc_count": 50, "model": "moss-minilm"},
        ]
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=fake_indexes):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--index", "docs",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data["indexes"]) == 1
        assert data["indexes"][0]["name"] == "docs"
        assert data["focus_index"] == "docs"

    def test_focus_index_not_found_shows_all(self, runner: CliRunner) -> None:
        """If focused index not found, show all indexes."""
        fake_indexes = [
            {"name": "docs", "status": "Ready", "doc_count": 100, "model": "moss-minilm"},
        ]
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=fake_indexes):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                    "--index", "nonexistent",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data["indexes"]) == 1

    def test_empty_indexes_when_no_credentials(self, runner: CliRunner) -> None:
        """Should have empty indexes when no credentials."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("MOSS_")}
        with patch("moss_cli.commands.agent_config.load_config", return_value={}), \
             patch.dict("os.environ", clean_env, clear=True):
            result = runner.invoke(
                app,
                ["--json", "agent-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["indexes"] == []


class TestAgentConfigHumanOutput:
    def test_human_output_contains_markdown(self, runner: CliRunner) -> None:
        """Human-readable output should contain markdown headers."""
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=[]):
            result = runner.invoke(
                app,
                [
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                ],
            )

        assert result.exit_code == 0
        assert "Moss Semantic Search" in result.stdout
        assert "Project ID" in result.stdout

    def test_human_output_with_indexes(self, runner: CliRunner) -> None:
        """Human output should show index details."""
        fake_indexes = [
            {"name": "my-docs", "status": "Ready", "doc_count": 42, "model": "moss-minilm"},
        ]
        with patch("moss_cli.commands.agent_config._fetch_indexes", return_value=fake_indexes):
            result = runner.invoke(
                app,
                [
                    "--project-id", "pid",
                    "--project-key", "pkey",
                    "agent-config",
                ],
            )

        assert result.exit_code == 0
        assert "my-docs" in result.stdout
        assert "42 docs" in result.stdout
