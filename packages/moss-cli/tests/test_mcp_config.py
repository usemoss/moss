"""Tests for moss mcp-config command."""

from __future__ import annotations

import os
from unittest.mock import patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import parse_json


class TestMcpConfigDefaults:
    def test_default_client_is_claude(self, runner: CliRunner) -> None:
        """Default client should be claude, outputting JSON config."""
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "claude"
        assert "config" in data
        assert "mcpServers" in data["config"]

    def test_placeholder_credentials_when_none_available(self, runner: CliRunner) -> None:
        """Should use placeholder values when no credentials are found."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("MOSS_")}
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}), \
             patch.dict("os.environ", clean_env, clear=True):
            result = runner.invoke(
                app,
                ["--json", "mcp-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        env = data["config"]["mcpServers"]["moss"]["env"]
        assert env["MOSS_PROJECT_ID"] == "<your-project-id>"
        assert env["MOSS_PROJECT_KEY"] == "<your-project-key>"

    def test_credentials_from_flags(self, runner: CliRunner) -> None:
        """Should use credentials from CLI flags."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--project-id", "my-pid",
                "--project-key", "my-pkey",
                "mcp-config",
            ],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        env = data["config"]["mcpServers"]["moss"]["env"]
        assert env["MOSS_PROJECT_ID"] == "my-pid"
        assert env["MOSS_PROJECT_KEY"] == "my-pkey"

    def test_credentials_from_config(self, runner: CliRunner) -> None:
        """Should resolve credentials from config file."""
        fake_config = {"project_id": "cfg-pid", "project_key": "cfg-pkey"}
        with patch("moss_cli.commands.mcp_config.load_config", return_value=fake_config):
            result = runner.invoke(
                app,
                ["--json", "mcp-config"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        env = data["config"]["mcpServers"]["moss"]["env"]
        assert env["MOSS_PROJECT_ID"] == "cfg-pid"
        assert env["MOSS_PROJECT_KEY"] == "cfg-pkey"


class TestMcpConfigClients:
    def test_claude_code_output(self, runner: CliRunner) -> None:
        """claude-code client should output text instructions."""
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "claude-code"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "claude-code"
        assert "instructions" in data
        assert "claude mcp add moss" in data["instructions"]

    def test_cursor_client(self, runner: CliRunner) -> None:
        """cursor client should produce JSON config."""
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "cursor"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "cursor"
        assert "mcpServers" in data["config"]

    def test_vscode_client(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "vscode"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "vscode"

    def test_windsurf_client(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "windsurf"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "windsurf"

    def test_other_client(self, runner: CliRunner) -> None:
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "other"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["client"] == "other"

    def test_unsupported_client_errors(self, runner: CliRunner) -> None:
        """Unsupported client should raise validation error."""
        result = runner.invoke(
            app,
            ["--json", "mcp-config", "--client", "emacs"],
        )

        assert result.exit_code != 0


class TestMcpConfigIndex:
    def test_index_flag_adds_env_var(self, runner: CliRunner) -> None:
        """--index should add MOSS_DEFAULT_INDEX to env config."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--project-id", "pid",
                "--project-key", "pkey",
                "mcp-config",
                "--index", "my-index",
            ],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        env = data["config"]["mcpServers"]["moss"]["env"]
        assert env["MOSS_DEFAULT_INDEX"] == "my-index"
        assert data["index"] == "my-index"

    def test_no_index_flag_omits_env_var(self, runner: CliRunner) -> None:
        """Without --index, MOSS_DEFAULT_INDEX should not be in env."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--project-id", "pid",
                "--project-key", "pkey",
                "mcp-config",
            ],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        env = data["config"]["mcpServers"]["moss"]["env"]
        assert "MOSS_DEFAULT_INDEX" not in env

    def test_claude_code_index_instruction(self, runner: CliRunner) -> None:
        """claude-code with --index should mention setting the env var."""
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["--json", "mcp-config", "--client", "claude-code", "--index", "my-idx"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert "MOSS_DEFAULT_INDEX" in data["instructions"]
        assert data["index"] == "my-idx"


class TestMcpConfigHumanOutput:
    def test_human_output_claude(self, runner: CliRunner) -> None:
        """Human-readable output should contain mcpServers."""
        result = runner.invoke(
            app,
            [
                "--project-id", "pid",
                "--project-key", "pkey",
                "mcp-config",
            ],
        )

        assert result.exit_code == 0
        assert "mcpServers" in result.stdout
        assert "moss" in result.stdout

    def test_human_output_claude_code(self, runner: CliRunner) -> None:
        """Human-readable claude-code output should show CLI command."""
        with patch("moss_cli.commands.mcp_config.load_config", return_value={}):
            result = runner.invoke(
                app,
                ["mcp-config", "--client", "claude-code"],
            )

        assert result.exit_code == 0
        assert "claude mcp add moss" in result.stdout


class TestMcpConfigJsonStructure:
    def test_json_config_structure(self, runner: CliRunner) -> None:
        """Verify the exact structure of the generated JSON config."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--project-id", "test-pid",
                "--project-key", "test-pkey",
                "mcp-config",
            ],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        config = data["config"]
        moss_server = config["mcpServers"]["moss"]
        assert moss_server["command"] == "npx"
        assert moss_server["args"] == ["-y", "@moss-tools/mcp-server"]
        assert "env" in moss_server
