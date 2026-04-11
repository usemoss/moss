"""Tests for --stdin alias on doc add and index create."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_mutation_result, parse_json


class TestDocAddStdin:
    def test_stdin_flag_reads_from_stdin(self, runner: CliRunner, mock_client) -> None:
        mut = make_mutation_result()
        mock_client.add_docs = AsyncMock(return_value=mut)

        docs_json = json.dumps([{"id": "1", "text": "from stdin"}])

        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "add", "test-index", "--stdin",
                ],
                input=docs_json,
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["job_id"] == "job_123"

    def test_stdin_and_file_together_errors(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "add", "test-index", "--stdin", "--file", "docs.json",
                ],
            )

        assert result.exit_code != 0

    def test_no_file_no_stdin_errors(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "add", "test-index",
                ],
            )

        assert result.exit_code != 0


class TestIndexCreateStdin:
    def test_stdin_flag_reads_from_stdin(self, runner: CliRunner, mock_client) -> None:
        mut = make_mutation_result()
        mock_client.create_index = AsyncMock(return_value=mut)

        docs_json = json.dumps([{"id": "1", "text": "from stdin"}])

        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "index", "create", "new-index", "--stdin",
                ],
                input=docs_json,
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["job_id"] == "job_123"

    def test_stdin_and_file_together_errors(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "index", "create", "new-index", "--stdin", "--file", "docs.json",
                ],
            )

        assert result.exit_code != 0

    def test_no_file_no_stdin_errors(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.index.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "index", "create", "new-index",
                ],
            )

        assert result.exit_code != 0
