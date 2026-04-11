"""Tests for moss doc commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from moss_cli.main import app

from .conftest import make_doc, make_mutation_result, parse_json


class TestDocAdd:
    def test_json_output(self, runner: CliRunner, mock_client) -> None:
        mut = make_mutation_result()
        mock_client.add_docs = AsyncMock(return_value=mut)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"id": "1", "text": "hello"}], f)
            f.flush()

            with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
                result = runner.invoke(
                    app,
                    [
                        "--json", "--project-id", "pid", "--project-key", "pkey",
                        "doc", "add", "test-index", "--file", f.name,
                    ],
                )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["job_id"] == "job_123"

    def test_stdin_input(self, runner: CliRunner, mock_client) -> None:
        mut = make_mutation_result()
        mock_client.add_docs = AsyncMock(return_value=mut)

        docs_json = json.dumps([{"id": "1", "text": "from stdin"}])

        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "add", "test-index", "--file", "-",
                ],
                input=docs_json,
            )

        assert result.exit_code == 0


class TestDocDelete:
    def test_json_output(self, runner: CliRunner, mock_client) -> None:
        mut = make_mutation_result()
        mock_client.delete_docs = AsyncMock(return_value=mut)

        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "delete", "test-index", "--ids", "doc-1,doc-2",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["job_id"] == "job_123"

    def test_empty_ids_fails(self, runner: CliRunner, mock_client) -> None:
        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "delete", "test-index", "--ids", "",
                ],
            )

        assert result.exit_code != 0


class TestDocGet:
    def test_json_output_all(self, runner: CliRunner, mock_client) -> None:
        docs = [make_doc(doc_id="d1"), make_doc(doc_id="d2", text="second")]
        mock_client.get_docs = AsyncMock(return_value=docs)

        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "get", "test-index",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data) == 2

    def test_json_output_by_ids(self, runner: CliRunner, mock_client) -> None:
        docs = [make_doc(doc_id="d1")]
        mock_client.get_docs = AsyncMock(return_value=docs)

        with patch("moss_cli.commands.doc.get_client", return_value=mock_client):
            result = runner.invoke(
                app,
                [
                    "--json", "--project-id", "pid", "--project-key", "pkey",
                    "doc", "get", "test-index", "--ids", "d1",
                ],
            )

        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert len(data) == 1
        assert data[0]["id"] == "d1"
