"""Tests for moss status command."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_index, parse_json


class TestStatusCommand:
    @patch("moss_cli.commands.status.get_client")
    def test_json_output_healthy(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(
            return_value=[
                make_index(name="idx-1", status="Ready"),
                make_index(name="idx-2", status="Ready"),
            ]
        )
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-id", "proj_abc123", "--project-key", "pk_live_test", "--json", "status"],
        )
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["project_id"] == "proj_abc123"
        assert data["data"]["indexes"] == 2
        assert data["data"]["indexes_healthy"] == 2

    @patch("moss_cli.commands.status.get_client")
    def test_json_output_mixed_health(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(
            return_value=[
                make_index(name="idx-1", status="Ready"),
                make_index(name="idx-2", status="Building"),
            ]
        )
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-id", "proj_abc123", "--project-key", "pk_live_test", "--json", "status"],
        )
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["data"]["indexes_healthy"] == 1

    @patch("moss_cli.commands.status.get_client")
    def test_human_output_all_healthy(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(
            return_value=[
                make_index(name="idx-1", status="Ready"),
                make_index(name="idx-2", status="active"),
            ]
        )
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-id", "proj_test", "--project-key", "pk_live_test", "status"],
        )
        assert result.exit_code == 0
        assert "proj_test" in result.stdout
        assert "2 indexes" in result.stdout
        assert "all healthy" in result.stdout

    @patch("moss_cli.commands.status.get_client")
    def test_human_output_partial_healthy(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(
            return_value=[
                make_index(name="idx-1", status="Ready"),
                make_index(name="idx-2", status="Error"),
                make_index(name="idx-3", status="Ready"),
            ]
        )
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-id", "proj_test", "--project-key", "pk_live_test", "status"],
        )
        assert result.exit_code == 0
        assert "2/3 healthy" in result.stdout

    @patch("moss_cli.commands.status.get_client")
    def test_human_output_no_indexes(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[])
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-id", "proj_test", "--project-key", "pk_live_test", "status"],
        )
        assert result.exit_code == 0
        assert "0 indexes" in result.stdout

    @patch("moss_cli.commands.status.get_client")
    @patch.dict("os.environ", {"MOSS_PROJECT_ID": "proj_env"}, clear=False)
    def test_project_id_from_env(
        self, mock_get_client: Mock, runner: CliRunner
    ) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[])
        mock_get_client.return_value = client

        result = runner.invoke(
            app,
            ["--project-key", "pk_live_test", "--json", "status"],
        )
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        # project_id should be resolved from env
        assert data["data"]["project_id"] == "proj_env"
