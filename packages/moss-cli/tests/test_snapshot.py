"""Tests for moss snapshot stub commands."""

from __future__ import annotations

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import parse_json


_HUMAN_MSG = "Index snapshots are not yet available."
_ROADMAP_URL = "https://docs.moss.dev/docs/roadmap"


class TestSnapshotCreate:
    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["snapshot", "create", "my-index"])
        assert result.exit_code == 0
        assert _HUMAN_MSG in result.stdout
        assert _ROADMAP_URL in result.stdout

    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "snapshot", "create", "my-index"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is False
        assert data["error"]["type"] == "not_implemented"
        assert "not yet available" in data["error"]["message"]

    def test_with_label_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["snapshot", "create", "my-index", "--label", "v1-backup"]
        )
        assert result.exit_code == 0
        assert _HUMAN_MSG in result.stdout


class TestSnapshotList:
    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["snapshot", "list", "my-index"])
        assert result.exit_code == 0
        assert _HUMAN_MSG in result.stdout
        assert _ROADMAP_URL in result.stdout

    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "snapshot", "list", "my-index"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is False
        assert data["error"]["type"] == "not_implemented"


class TestSnapshotRestore:
    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["snapshot", "restore", "my-index", "snap_abc123"]
        )
        assert result.exit_code == 0
        assert _HUMAN_MSG in result.stdout
        assert _ROADMAP_URL in result.stdout

    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["--json", "snapshot", "restore", "my-index", "snap_abc123"]
        )
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is False
        assert data["error"]["type"] == "not_implemented"


class TestSnapshotDelete:
    def test_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["snapshot", "delete", "snap_abc123"])
        assert result.exit_code == 0
        assert _HUMAN_MSG in result.stdout
        assert _ROADMAP_URL in result.stdout

    def test_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--json", "snapshot", "delete", "snap_abc123"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is False
        assert data["error"]["type"] == "not_implemented"
