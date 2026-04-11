"""Tests for moss query command."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_search_result, parse_json


class TestQueryCommand:
    def test_json_output(self, runner: CliRunner, mock_client) -> None:
        result_obj = make_search_result()
        mock_client.query = AsyncMock(return_value=result_obj)
        mock_client.load_index = AsyncMock()

        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index", "hello world",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["query"] == "test query"
        assert len(data["docs"]) == 1
        assert data["docs"][0]["score"] == 0.95

    def test_stdin_query(self, runner: CliRunner, mock_client) -> None:
        result_obj = make_search_result(query="piped query")
        mock_client.query = AsyncMock(return_value=result_obj)
        mock_client.load_index = AsyncMock()

        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index",
                ],
                input="piped query\n",
            )

        assert result.exit_code == 0

    def test_invalid_filter_json(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index", "hello",
                    "--filter", "not-valid-json",
                ],
            )

        assert result.exit_code != 0

    def test_cloud_with_filter_rejected(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index", "hello",
                    "--cloud", "--filter", '{"key": "val"}',
                ],
            )

        assert result.exit_code != 0

    def test_cloud_query_skips_load(self, runner: CliRunner, mock_client) -> None:
        result_obj = make_search_result()
        mock_client.query = AsyncMock(return_value=result_obj)
        mock_client.load_index = AsyncMock()

        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index", "hello", "--cloud",
                ],
            )

        mock_client.load_index.assert_not_awaited()
