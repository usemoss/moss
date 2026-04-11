"""Tests for output.py _print_json envelope behavior."""

from __future__ import annotations

import json

from moss_cli.output import _print_json


class TestPrintJsonEnvelope:
    def test_no_envelope(self, capsys) -> None:
        _print_json({"key": "value"})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data == {"key": "value"}
        assert "ok" not in data

    def test_envelope_wraps_data(self, capsys) -> None:
        _print_json({"key": "value"}, envelope=True, command="test cmd")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"] == {"key": "value"}
        assert data["meta"]["command"] == "test cmd"

    def test_envelope_without_command(self, capsys) -> None:
        _print_json([1, 2, 3], envelope=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"] == [1, 2, 3]
        assert "meta" not in data

    def test_envelope_with_empty_data(self, capsys) -> None:
        _print_json([], envelope=True, command="index list")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"] == []
        assert data["meta"]["command"] == "index list"
