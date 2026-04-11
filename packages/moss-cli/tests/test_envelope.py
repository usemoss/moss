"""Tests for --json-envelope wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_index, make_mutation_result, make_search_result, parse_json


class TestEnvelopeIndexList:
    def test_envelope_wraps_data(self, runner: CliRunner, mock_client) -> None:
        indexes = [make_index(name="idx-a")]
        mock_client.list_indexes = AsyncMock(return_value=indexes)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--json-envelope",
                    "--project-id", "pid", "--project-key", "pkey",
                    "index", "list",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert isinstance(data["data"], list)
        assert data["data"][0]["name"] == "idx-a"
        assert data["meta"]["command"] == "index list"

    def test_no_envelope_by_default(self, runner: CliRunner, mock_client) -> None:
        indexes = [make_index(name="idx-a")]
        mock_client.list_indexes = AsyncMock(return_value=indexes)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json",
                    "--project-id", "pid", "--project-key", "pkey",
                    "index", "list",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        # Without envelope, output is just the array directly
        assert isinstance(data, list)
        assert "ok" not in data[0] if data else True


class TestEnvelopeIndexGet:
    def test_envelope_wraps_detail(self, runner: CliRunner, mock_client) -> None:
        idx = make_index(name="my-index")
        mock_client.get_index = AsyncMock(return_value=idx)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--json-envelope",
                    "--project-id", "pid", "--project-key", "pkey",
                    "index", "get", "my-index",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["name"] == "my-index"
        assert data["meta"]["command"] == "index get"


class TestEnvelopeIndexDelete:
    def test_envelope_wraps_success(self, runner: CliRunner, mock_client) -> None:
        mock_client.delete_index = AsyncMock(return_value=True)

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--json-envelope", "--yes",
                    "--project-id", "pid", "--project-key", "pkey",
                    "index", "delete", "my-index",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["status"] == "ok"
        assert data["meta"]["command"] == "index delete"


class TestEnvelopeQuery:
    def test_envelope_wraps_search(self, runner: CliRunner, mock_client) -> None:
        result_obj = make_search_result()
        mock_client.query = AsyncMock(return_value=result_obj)
        mock_client.load_index = AsyncMock()

        with patch("moss_cli.commands.search.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--json-envelope",
                    "--project-id", "pid", "--project-key", "pkey",
                    "query", "test-index", "hello world",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["query"] == "test query"
        assert data["meta"]["command"] == "query"


class TestEnvelopeVersion:
    def test_envelope_wraps_version(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["--json", "--json-envelope", "version"],
        )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert "cli" in data["data"]
        assert "sdk" in data["data"]
        assert "python" in data["data"]
        assert data["meta"]["command"] == "version"
