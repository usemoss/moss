"""Tests for error hierarchy and SDK normalization."""

from __future__ import annotations

import pytest

from moss_cli.errors import (
    CliAuthError,
    CliError,
    CliNetworkError,
    CliSdkError,
    CliUserAbortError,
    CliValidationError,
    normalize_exception,
)


class TestCliErrorHierarchy:
    def test_base_error_defaults(self) -> None:
        e = CliError("something broke")
        assert e.message == "something broke"
        assert e.exit_code == 1
        assert e.error_type == "cli_error"
        assert e.hint == ""
        assert e.retryable is False
        assert e.details == {}

    def test_base_error_with_all_fields(self) -> None:
        e = CliError(
            "bad thing",
            hint="try again",
            retryable=True,
            details={"key": "val"},
        )
        d = e.to_dict()
        assert d["type"] == "cli_error"
        assert d["message"] == "bad thing"
        assert d["hint"] == "try again"
        assert d["retryable"] is True
        assert d["details"] == {"key": "val"}

    def test_to_dict_omits_empty_hint(self) -> None:
        e = CliError("msg")
        d = e.to_dict()
        assert "hint" not in d

    def test_to_dict_omits_empty_details(self) -> None:
        e = CliError("msg")
        d = e.to_dict()
        assert "details" not in d

    def test_subclass_exit_codes(self) -> None:
        assert CliSdkError("x").exit_code == 1
        assert CliAuthError("x").exit_code == 3
        assert CliValidationError("x").exit_code == 2
        assert CliNetworkError("x").exit_code == 5
        assert CliUserAbortError("x").exit_code == 130

    def test_subclass_error_types(self) -> None:
        assert CliSdkError("x").error_type == "sdk_error"
        assert CliAuthError("x").error_type == "auth_error"
        assert CliValidationError("x").error_type == "validation_error"
        assert CliNetworkError("x").error_type == "network_error"
        assert CliUserAbortError("x").error_type == "user_abort"

    def test_is_exception(self) -> None:
        with pytest.raises(CliError):
            raise CliError("test")

    def test_subclass_is_cli_error(self) -> None:
        with pytest.raises(CliError):
            raise CliAuthError("test")


class TestNormalizeException:
    def test_passthrough_cli_error(self) -> None:
        orig = CliAuthError("already typed")
        result = normalize_exception(orig)
        assert result is orig

    def test_http_401(self) -> None:
        exc = RuntimeError("HTTP error! status: 401")
        result = normalize_exception(exc)
        assert isinstance(result, CliAuthError)
        assert result.exit_code == 3

    def test_http_403(self) -> None:
        exc = RuntimeError("HTTP error! status: 403")
        result = normalize_exception(exc)
        assert isinstance(result, CliAuthError)

    def test_http_404(self) -> None:
        exc = RuntimeError("HTTP error! status: 404")
        result = normalize_exception(exc)
        assert isinstance(result, CliValidationError)
        assert result.exit_code == 2

    def test_http_429(self) -> None:
        exc = RuntimeError("HTTP error! status: 429")
        result = normalize_exception(exc)
        assert isinstance(result, CliNetworkError)
        assert result.retryable is True
        assert result.exit_code == 5

    def test_http_400(self) -> None:
        exc = RuntimeError("HTTP error! status: 400")
        result = normalize_exception(exc)
        assert isinstance(result, CliValidationError)

    def test_http_409(self) -> None:
        exc = RuntimeError("HTTP error! status: 409")
        result = normalize_exception(exc)
        assert isinstance(result, CliValidationError)

    def test_http_500(self) -> None:
        exc = RuntimeError("HTTP error! status: 500")
        result = normalize_exception(exc)
        assert isinstance(result, CliNetworkError)
        assert result.retryable is True

    def test_http_502(self) -> None:
        exc = RuntimeError("HTTP error! status: 502")
        result = normalize_exception(exc)
        assert isinstance(result, CliNetworkError)

    def test_missing_credentials_pattern(self) -> None:
        exc = Exception("Missing credentials. Provide --project-id/--project-key...")
        result = normalize_exception(exc)
        assert isinstance(result, CliAuthError)
        assert "moss init" in result.hint

    def test_cloud_query_failed_pattern(self) -> None:
        exc = RuntimeError("Cloud query request failed: timeout")
        result = normalize_exception(exc)
        assert isinstance(result, CliNetworkError)
        assert result.retryable is True

    def test_requires_embeddings_pattern(self) -> None:
        exc = RuntimeError("Index 'custom-idx' requires explicit query embeddings")
        result = normalize_exception(exc)
        assert isinstance(result, CliValidationError)

    def test_unknown_fallback(self) -> None:
        exc = RuntimeError("something completely unexpected")
        result = normalize_exception(exc)
        assert isinstance(result, CliSdkError)
        assert result.exit_code == 1

    def test_preserves_original_message(self) -> None:
        msg = "HTTP error! status: 404 - Index 'foo' not found"
        exc = RuntimeError(msg)
        result = normalize_exception(exc)
        assert result.message == msg
