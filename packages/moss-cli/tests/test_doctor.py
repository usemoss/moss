"""Tests for moss doctor command and individual checks."""

from __future__ import annotations

import json
import types
from unittest.mock import AsyncMock, Mock, patch

import pytest
from typer.testing import CliRunner

from moss_cli.checks import (
    CheckResult,
    check_api_reachable,
    check_cli_version,
    check_credentials_valid,
    check_dns_resolution,
    check_indexes,
    check_key_format,
    check_node_available,
    check_onnx_available,
    check_project_id_set,
    check_project_key_set,
    check_python_version,
    check_sdk_version,
    run_all_checks,
)
from moss_cli.main import app

from .conftest import make_index, parse_json


# ---------------------------------------------------------------------------
# CheckResult dataclass
# ---------------------------------------------------------------------------


class TestCheckResult:
    def test_to_dict_minimal(self) -> None:
        r = CheckResult(
            category="test", name="t", status="pass", detail="ok"
        )
        d = r.to_dict()
        assert d == {
            "category": "test",
            "name": "t",
            "status": "pass",
            "detail": "ok",
        }
        assert "fix" not in d

    def test_to_dict_with_fix(self) -> None:
        r = CheckResult(
            category="test", name="t", status="fail", detail="bad", fix="do X"
        )
        d = r.to_dict()
        assert d["fix"] == "do X"


# ---------------------------------------------------------------------------
# Credential checks
# ---------------------------------------------------------------------------


class TestCheckProjectIdSet:
    @patch.dict("os.environ", {"MOSS_PROJECT_ID": "proj_abc12345"}, clear=False)
    def test_pass_from_env(self) -> None:
        r = check_project_id_set()
        assert r.status == "pass"
        assert "proj_abc" in r.detail

    @patch.dict("os.environ", {}, clear=False)
    @patch("moss_cli.checks.load_config", return_value={"project_id": "proj_from_config"})
    def test_pass_from_config(self, _mock_cfg: Mock) -> None:
        # Remove env var if present
        import os
        os.environ.pop("MOSS_PROJECT_ID", None)
        r = check_project_id_set()
        assert r.status == "pass"

    @patch.dict("os.environ", {}, clear=False)
    @patch("moss_cli.checks.load_config", return_value={})
    def test_fail_when_missing(self, _mock_cfg: Mock) -> None:
        import os
        os.environ.pop("MOSS_PROJECT_ID", None)
        r = check_project_id_set()
        assert r.status == "fail"
        assert r.fix


class TestCheckProjectKeySet:
    @patch.dict("os.environ", {"MOSS_PROJECT_KEY": "pk_live_abc12345"}, clear=False)
    def test_pass_from_env(self) -> None:
        r = check_project_key_set()
        assert r.status == "pass"

    @patch.dict("os.environ", {}, clear=False)
    @patch("moss_cli.checks.load_config", return_value={})
    def test_fail_when_missing(self, _mock_cfg: Mock) -> None:
        import os
        os.environ.pop("MOSS_PROJECT_KEY", None)
        r = check_project_key_set()
        assert r.status == "fail"


class TestCheckKeyFormat:
    @patch.dict("os.environ", {"MOSS_PROJECT_KEY": "pk_live_abc123"}, clear=False)
    def test_pass_pk_live(self) -> None:
        r = check_key_format()
        assert r.status == "pass"

    @patch.dict("os.environ", {"MOSS_PROJECT_KEY": "ak_live_abc123"}, clear=False)
    def test_pass_ak_live(self) -> None:
        r = check_key_format()
        assert r.status == "pass"

    @patch.dict("os.environ", {"MOSS_PROJECT_KEY": "invalid_prefix_abc"}, clear=False)
    def test_warn_bad_prefix(self) -> None:
        r = check_key_format()
        assert r.status == "warn"
        assert r.fix

    @patch.dict("os.environ", {}, clear=False)
    @patch("moss_cli.checks.load_config", return_value={})
    def test_fail_when_no_key(self, _mock_cfg: Mock) -> None:
        import os
        os.environ.pop("MOSS_PROJECT_KEY", None)
        r = check_key_format()
        assert r.status == "fail"


class TestCheckCredentialsValid:
    def test_pass_when_list_indexes_works(self) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[])
        r = check_credentials_valid(client)
        assert r.status == "pass"

    def test_fail_when_list_indexes_raises(self) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(side_effect=RuntimeError("401 Unauthorized"))
        r = check_credentials_valid(client)
        assert r.status == "fail"
        assert "401" in r.detail

    def test_fail_when_client_is_none(self) -> None:
        r = check_credentials_valid(None)
        assert r.status == "fail"


# ---------------------------------------------------------------------------
# Connectivity checks
# ---------------------------------------------------------------------------


class TestCheckDnsResolution:
    @patch("moss_cli.checks.socket.getaddrinfo", return_value=[
        (2, 1, 6, "", ("1.2.3.4", 443))
    ])
    def test_pass(self, _mock: Mock) -> None:
        r = check_dns_resolution()
        assert r.status == "pass"
        assert "1.2.3.4" in r.detail

    @patch("moss_cli.checks.socket.getaddrinfo", side_effect=__import__("socket").gaierror("no host"))
    def test_fail(self, _mock: Mock) -> None:
        r = check_dns_resolution()
        assert r.status == "fail"
        assert "DNS" in r.detail


class TestCheckApiReachable:
    @patch("moss_cli.checks.urllib.request.urlopen")
    def test_pass(self, mock_urlopen: Mock) -> None:
        mock_resp = Mock()
        mock_resp.status = 200
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        r = check_api_reachable()
        assert r.status == "pass"
        assert "reachable" in r.detail

    @patch("moss_cli.checks.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_fail(self, _mock: Mock) -> None:
        r = check_api_reachable()
        assert r.status == "fail"
        assert "timeout" in r.detail


# ---------------------------------------------------------------------------
# Version checks
# ---------------------------------------------------------------------------


class TestCheckCliVersion:
    @patch("moss_cli.checks.urllib.request.urlopen")
    @patch("moss_cli.checks.importlib.metadata.version", return_value="1.0.0")
    def test_pass_up_to_date(self, _mock_ver: Mock, mock_urlopen: Mock) -> None:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"info": {"version": "1.0.0"}}).encode()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        r = check_cli_version()
        assert r.status == "pass"
        assert "up to date" in r.detail

    @patch("moss_cli.checks.urllib.request.urlopen")
    @patch("moss_cli.checks.importlib.metadata.version", return_value="0.9.0")
    def test_warn_outdated(self, _mock_ver: Mock, mock_urlopen: Mock) -> None:
        mock_resp = Mock()
        mock_resp.read.return_value = json.dumps({"info": {"version": "1.0.0"}}).encode()
        mock_resp.__enter__ = Mock(return_value=mock_resp)
        mock_resp.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        r = check_cli_version()
        assert r.status == "warn"
        assert "1.0.0" in r.detail
        assert r.fix

    @patch("moss_cli.checks.urllib.request.urlopen", side_effect=Exception("no network"))
    @patch("moss_cli.checks.importlib.metadata.version", return_value="0.9.0")
    def test_warn_pypi_unreachable(self, _mock_ver: Mock, _mock_url: Mock) -> None:
        r = check_cli_version()
        assert r.status == "warn"
        assert "could not check" in r.detail


class TestCheckSdkVersion:
    @patch("moss_cli.checks.importlib.metadata.version", return_value="2.0.0")
    def test_pass(self, _mock: Mock) -> None:
        r = check_sdk_version()
        assert r.status == "pass"
        assert "2.0.0" in r.detail

    @patch(
        "moss_cli.checks.importlib.metadata.version",
        side_effect=__import__("importlib").metadata.PackageNotFoundError("moss"),
    )
    def test_fail_not_installed(self, _mock: Mock) -> None:
        r = check_sdk_version()
        assert r.status == "fail"
        assert r.fix


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------


class TestCheckPythonVersion:
    @patch("moss_cli.checks.sys.version_info", new=(3, 12, 1, "final", 0))
    def test_pass(self) -> None:
        r = check_python_version()
        assert r.status == "pass"

    @patch("moss_cli.checks.sys.version_info", new=(3, 9, 1, "final", 0))
    def test_fail(self) -> None:
        r = check_python_version()
        assert r.status == "fail"
        assert "3.10+" in r.detail


class TestCheckNodeAvailable:
    @patch("moss_cli.checks.subprocess.run")
    @patch("moss_cli.checks.shutil.which", return_value="/usr/bin/node")
    def test_pass(self, _mock_which: Mock, mock_run: Mock) -> None:
        mock_run.return_value = Mock(stdout="v20.10.0\n")
        r = check_node_available()
        assert r.status == "pass"
        assert "v20.10.0" in r.detail

    @patch("moss_cli.checks.shutil.which", return_value=None)
    def test_warn_not_found(self, _mock: Mock) -> None:
        r = check_node_available()
        assert r.status == "warn"
        assert "not found" in r.detail


class TestCheckOnnxAvailable:
    @patch("moss_cli.checks.importlib.import_module")
    def test_pass(self, mock_import: Mock) -> None:
        fake_ort = types.SimpleNamespace(__version__="1.17.0")
        mock_import.return_value = fake_ort
        r = check_onnx_available()
        assert r.status == "pass"
        assert "1.17.0" in r.detail

    @patch("moss_cli.checks.importlib.import_module", side_effect=ImportError("no ort"))
    def test_warn_not_installed(self, _mock: Mock) -> None:
        r = check_onnx_available()
        assert r.status == "warn"
        assert r.fix


# ---------------------------------------------------------------------------
# Index checks
# ---------------------------------------------------------------------------


class TestCheckIndexes:
    def test_pass_all_recent(self) -> None:
        idx = make_index(updated_at="2026-04-09T00:00:00Z")
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[idx])
        r = check_indexes(client)
        assert r.status == "pass"
        assert "1 index" in r.detail

    def test_warn_stale(self) -> None:
        idx = make_index(name="old-index", updated_at="2025-01-01T00:00:00Z")
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[idx])
        r = check_indexes(client)
        assert r.status == "warn"
        assert "stale" in r.detail
        assert "old-index" in r.detail

    def test_warn_no_indexes(self) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(return_value=[])
        r = check_indexes(client)
        assert r.status == "warn"
        assert "No indexes" in r.detail

    def test_fail_no_client(self) -> None:
        r = check_indexes(None)
        assert r.status == "fail"

    def test_fail_on_exception(self) -> None:
        client = Mock()
        client.list_indexes = AsyncMock(side_effect=RuntimeError("network"))
        r = check_indexes(client)
        assert r.status == "fail"


# ---------------------------------------------------------------------------
# run_all_checks orchestrator
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    @patch("moss_cli.checks.check_indexes")
    @patch("moss_cli.checks.check_onnx_available")
    @patch("moss_cli.checks.check_node_available")
    @patch("moss_cli.checks.check_python_version")
    @patch("moss_cli.checks.check_sdk_version")
    @patch("moss_cli.checks.check_cli_version")
    @patch("moss_cli.checks.check_api_reachable")
    @patch("moss_cli.checks.check_dns_resolution")
    @patch("moss_cli.checks.check_credentials_valid")
    @patch("moss_cli.checks.check_key_format")
    @patch("moss_cli.checks.check_project_key_set")
    @patch("moss_cli.checks.check_project_id_set")
    def test_returns_all_results(self, *mocks: Mock) -> None:
        for m in mocks:
            m.return_value = CheckResult(
                category="test", name="t", status="pass", detail="ok"
            )
        results = run_all_checks(client=None)
        assert len(results) == 12
        for m in mocks:
            m.assert_called_once()


# ---------------------------------------------------------------------------
# Doctor CLI command
# ---------------------------------------------------------------------------


class TestDoctorCommand:
    @patch("moss_cli.commands.doctor.run_all_checks")
    @patch("moss_cli.commands.doctor.get_client", return_value=Mock())
    def test_json_output_all_pass(
        self, _mock_client: Mock, mock_checks: Mock, runner: CliRunner
    ) -> None:
        mock_checks.return_value = [
            CheckResult(category="test", name="a", status="pass", detail="ok"),
            CheckResult(category="test", name="b", status="pass", detail="ok"),
        ]
        result = runner.invoke(app, ["--json", "doctor"])
        assert result.exit_code == 0
        data = parse_json(result.stdout)
        assert data["ok"] is True
        assert data["data"]["summary"]["pass"] == 2
        assert data["data"]["summary"]["fail"] == 0

    @patch("moss_cli.commands.doctor.run_all_checks")
    @patch("moss_cli.commands.doctor.get_client", return_value=Mock())
    def test_json_output_with_failure(
        self, _mock_client: Mock, mock_checks: Mock, runner: CliRunner
    ) -> None:
        mock_checks.return_value = [
            CheckResult(category="cred", name="a", status="pass", detail="ok"),
            CheckResult(category="cred", name="b", status="fail", detail="bad"),
        ]
        result = runner.invoke(app, ["--json", "doctor"])
        assert result.exit_code == 1
        data = parse_json(result.stdout)
        assert data["ok"] is False
        assert data["data"]["summary"]["fail"] == 1

    @patch("moss_cli.commands.doctor.run_all_checks")
    @patch("moss_cli.commands.doctor.get_client", return_value=Mock())
    def test_human_output(
        self, _mock_client: Mock, mock_checks: Mock, runner: CliRunner
    ) -> None:
        mock_checks.return_value = [
            CheckResult(category="credentials", name="a", status="pass", detail="ok"),
            CheckResult(category="connectivity", name="b", status="warn", detail="slow"),
        ]
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "PASS" in result.stdout
        assert "WARN" in result.stdout

    @patch("moss_cli.commands.doctor.run_all_checks")
    @patch("moss_cli.commands.doctor.get_client", return_value=Mock())
    def test_fix_flag_shows_fixes(
        self, _mock_client: Mock, mock_checks: Mock, runner: CliRunner
    ) -> None:
        mock_checks.return_value = [
            CheckResult(
                category="versions",
                name="cli",
                status="warn",
                detail="outdated",
                fix="pip install --upgrade moss-cli",
            ),
        ]
        result = runner.invoke(app, ["doctor", "--fix"])
        assert result.exit_code == 0
        assert "pip install" in result.stdout

    @patch("moss_cli.commands.doctor.run_all_checks")
    @patch("moss_cli.commands.doctor.get_client", side_effect=Exception("no creds"))
    def test_runs_without_client(
        self, _mock_client: Mock, mock_checks: Mock, runner: CliRunner
    ) -> None:
        mock_checks.return_value = [
            CheckResult(category="cred", name="a", status="fail", detail="no creds"),
        ]
        result = runner.invoke(app, ["--json", "doctor"])
        # Should still produce output, just with failures
        assert result.exit_code == 1
        data = parse_json(result.stdout)
        assert data["ok"] is False
