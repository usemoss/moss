"""Tests for moss init command."""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import parse_json


class TestInitJsonMode:
    def test_json_yes_with_credentials(self, runner: CliRunner) -> None:
        """--json --yes --project-id X --project-key Y saves config and outputs JSON."""
        with patch("moss_cli.commands.init_cmd.save_config") as mock_save, \
             patch("moss_cli.commands.init_cmd.get_config_path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.__str__ = lambda self: "/mock/.moss/config.json"
            result = runner.invoke(
                app,
                [
                    "--json", "--yes",
                    "--project-id", "test-pid",
                    "--project-key", "test-pkey",
                    "init",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "ok"
        assert "config_path" in data
        mock_save.assert_called_once_with({"project_id": "test-pid", "project_key": "test-pkey"})

    def test_json_without_yes_errors(self, runner: CliRunner) -> None:
        """--json without --yes should error because init is interactive."""
        result = runner.invoke(
            app,
            [
                "--json",
                "--project-id", "test-pid",
                "--project-key", "test-pkey",
                "init",
            ],
        )

        assert result.exit_code != 0

    def test_yes_without_credentials_errors(self, runner: CliRunner) -> None:
        """--yes without credentials should error."""
        result = runner.invoke(
            app,
            ["--json", "--yes", "init"],
        )

        assert result.exit_code != 0

    def test_json_yes_envelope(self, runner: CliRunner) -> None:
        """--json --json-envelope --yes wraps output in envelope."""
        with patch("moss_cli.commands.init_cmd.save_config"), \
             patch("moss_cli.commands.init_cmd.get_config_path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.__str__ = lambda self: "/mock/.moss/config.json"
            result = runner.invoke(
                app,
                [
                    "--json", "--json-envelope", "--yes",
                    "--project-id", "test-pid",
                    "--project-key", "test-pkey",
                    "init",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["status"] == "ok"
        assert data["meta"]["command"] == "init"
