"""Tests for moss index commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_index, make_mutation_result, parse_json


class TestIndexList:
    def test_json_output(self, runner: CliRunner, mock_client) -> None:
        indexes = [make_index(name="idx-a"), make_index(name="idx-b", doc_count=200)]
        mock_client.list_indexes = AsyncMock(return_value=indexes)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "--project-id", "pid", "--project-key", "pkey", "index", "list"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data) == 2
        assert data[0]["name"] == "idx-a"
        assert data[1]["name"] == "idx-b"
        assert data[1]["doc_count"] == 200

    def test_empty_list(self, runner: CliRunner, mock_client) -> None:
        mock_client.list_indexes = AsyncMock(return_value=[])

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "--project-id", "pid", "--project-key", "pkey", "index", "list"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data == []

    def test_human_output(self, runner: CliRunner, mock_client) -> None:
        mock_client.list_indexes = AsyncMock(return_value=[make_index()])

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--project-id", "pid", "--project-key", "pkey", "index", "list"],
            )

        assert result.exit_code == 0
        assert "test-index" in result.stdout


class TestIndexGet:
    def test_json_output(self, runner: CliRunner, mock_client) -> None:
        idx = make_index(name="my-index", doc_count=42)
        mock_client.get_index = AsyncMock(return_value=idx)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "--project-id", "pid", "--project-key", "pkey", "index", "get", "my-index"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["name"] == "my-index"
        assert data["doc_count"] == 42


class TestIndexDelete:
    def test_json_with_yes_flag(self, runner: CliRunner, mock_client) -> None:
        mock_client.delete_index = AsyncMock(return_value=True)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "--yes", "--project-id", "pid", "--project-key", "pkey", "index", "delete", "my-index"],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["status"] == "ok"

    def test_delete_failure_exits_nonzero(self, runner: CliRunner, mock_client) -> None:
        mock_client.delete_index = AsyncMock(return_value=False)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                ["--json", "--yes", "--project-id", "pid", "--project-key", "pkey", "index", "delete", "my-index"],
            )

        # CliSdkError has exit_code 1
        assert result.exit_code == 1
