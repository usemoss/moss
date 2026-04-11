"""Tests for moss experimental commands (provision, keys)."""

from __future__ import annotations

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import parse_json


class TestProvision:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "experimental", "provision"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "unavailable"
        assert "portal.usemoss.dev" in data["message"]

    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["experimental", "provision"],
        )

        assert result.exit_code == 0
        assert "not yet available" in result.stdout
        assert "portal.usemoss.dev" in result.stdout


class TestKeysCreate:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "experimental", "keys", "create"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "unavailable"
        assert "not yet available" in data["message"]

    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["experimental", "keys", "create"],
        )

        assert result.exit_code == 0
        assert "not yet available" in result.stdout


class TestKeysList:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "experimental", "keys", "list"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "unavailable"


class TestKeysRevoke:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "experimental", "keys", "revoke"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "unavailable"


class TestKeysRotate:
    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "experimental", "keys", "rotate"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "unavailable"
