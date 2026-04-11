"""Tests for moss version command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import parse_json


class TestVersionCommand:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "version"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert "cli" in data
        assert "sdk" in data
        assert "python" in data

    def test_json_python_version_format(self, runner: CliRunner) -> None:
        import sys

        result = runner.invoke(app, ["--json", "version"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert data["python"] == expected

    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "moss-cli" in result.stdout
        assert "moss SDK" in result.stdout
        assert "Python" in result.stdout
