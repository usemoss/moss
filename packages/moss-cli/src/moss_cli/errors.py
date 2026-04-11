"""Structured CLI errors with exit code mapping and SDK normalization."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


class CliError(Exception):
    """Base CLI error with structured output support."""

    error_type: str = "cli_error"
    exit_code: int = 1

    def __init__(
        self,
        message: str,
        *,
        hint: str = "",
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.error_type,
            "message": self.message,
        }
        if self.hint:
            d["hint"] = self.hint
        d["retryable"] = self.retryable
        if self.details:
            d["details"] = self.details
        return d


class CliSdkError(CliError):
    """Unexpected SDK/backend error."""

    error_type = "sdk_error"
    exit_code = 1


class CliAuthError(CliError):
    """Authentication or authorization failure."""

    error_type = "auth_error"
    exit_code = 3


class CliValidationError(CliError):
    """Invalid input, missing resource, or bad request."""

    error_type = "validation_error"
    exit_code = 2


class CliNetworkError(CliError):
    """Network connectivity, timeout, or rate-limit error."""

    error_type = "network_error"
    exit_code = 5


class CliUserAbortError(CliError):
    """User cancelled the operation."""

    error_type = "user_abort"
    exit_code = 130


# --- SDK error normalization ---

_HTTP_STATUS_RE = re.compile(
    r"HTTP\s*(?:error!?\s*status:\s*|)(\d{3})",
    re.IGNORECASE,
)

_STATUS_MAP: list[tuple[range, type[CliError]]] = [
    (range(401, 404), CliAuthError),       # 401, 402, 403
    (range(404, 405), CliValidationError),  # 404
    (range(429, 430), CliNetworkError),     # 429 rate limit
    (range(400, 400), CliValidationError),  # 400 (handled below)
    (range(500, 600), CliNetworkError),     # 5xx server errors
]

# Status codes that map to validation errors
_VALIDATION_STATUSES = {400, 404, 409, 413, 422}
# Status codes that map to auth errors
_AUTH_STATUSES = {401, 402, 403}
# Status codes that map to network/rate-limit errors
_NETWORK_STATUSES = {429, 502, 503, 504}


def _classify_http_status(status: int) -> type[CliError]:
    if status in _AUTH_STATUSES:
        return CliAuthError
    if status in _VALIDATION_STATUSES:
        return CliValidationError
    if status in _NETWORK_STATUSES:
        return CliNetworkError
    if 500 <= status < 600:
        return CliNetworkError
    return CliSdkError


_PATTERN_MAP: list[tuple[str, type[CliError], dict[str, Any]]] = [
    (
        r"Missing credentials",
        CliAuthError,
        {"hint": "Run 'moss init' to save credentials or set MOSS_PROJECT_ID/MOSS_PROJECT_KEY."},
    ),
    (
        r"Cloud query request failed",
        CliNetworkError,
        {"hint": "Check your network connection or try again later.", "retryable": True},
    ),
    (
        r"requires explicit query embeddings",
        CliValidationError,
        {"hint": "This index uses custom embeddings. Provide an embedding with your query."},
    ),
]


def normalize_exception(exc: Exception) -> CliError:
    """Convert a generic exception into a typed CliError.

    Classifies SDK RuntimeError/Exception strings by matching HTTP status
    codes and known error patterns from the Rust bindings.
    """
    if isinstance(exc, CliError):
        return exc

    msg = str(exc)

    # Try HTTP status code extraction first
    match = _HTTP_STATUS_RE.search(msg)
    if match:
        status = int(match.group(1))
        cls = _classify_http_status(status)
        retryable = status in _NETWORK_STATUSES or (500 <= status < 600)
        return cls(msg, retryable=retryable)

    # Try known pattern matching
    for pattern, cls, kwargs in _PATTERN_MAP:
        if re.search(pattern, msg, re.IGNORECASE):
            return cls(msg, **kwargs)

    # Fallback
    return CliSdkError(msg)
