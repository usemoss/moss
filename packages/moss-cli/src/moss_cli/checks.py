"""Diagnostic checks for `moss doctor`."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from .config import load_config


@dataclass(slots=True)
class CheckResult:
    """Result of a single diagnostic check."""

    category: str  # credentials, connectivity, sdk_versions, environment, indexes
    name: str  # e.g. "project_id_set"
    status: str  # "pass", "warn", "fail"
    detail: str  # human-readable message
    fix: str = ""  # optional fix command

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }
        if self.fix:
            d["fix"] = self.fix
        return d


# ---------------------------------------------------------------------------
# Credential checks
# ---------------------------------------------------------------------------


def _resolve_value(name: str, env_var: str, config_key: str) -> Optional[str]:
    """Resolve a value from env var or config file."""
    val = os.environ.get(env_var)
    if val:
        return val
    cfg = load_config()
    return cfg.get(config_key)


def check_project_id_set() -> CheckResult:
    """Check that MOSS_PROJECT_ID is available."""
    val = _resolve_value("project_id", "MOSS_PROJECT_ID", "project_id")
    if val:
        return CheckResult(
            category="credentials",
            name="project_id_set",
            status="pass",
            detail=f"Project ID is set ({val[:8]}...).",
        )
    return CheckResult(
        category="credentials",
        name="project_id_set",
        status="fail",
        detail="Project ID is not set.",
        fix="export MOSS_PROJECT_ID=<your-project-id>  # or run: moss init",
    )


def check_project_key_set() -> CheckResult:
    """Check that MOSS_PROJECT_KEY is available."""
    val = _resolve_value("project_key", "MOSS_PROJECT_KEY", "project_key")
    if val:
        masked = val[:8] + "..." if len(val) > 8 else "***"
        return CheckResult(
            category="credentials",
            name="project_key_set",
            status="pass",
            detail=f"Project key is set ({masked}).",
        )
    return CheckResult(
        category="credentials",
        name="project_key_set",
        status="fail",
        detail="Project key is not set.",
        fix="export MOSS_PROJECT_KEY=<your-project-key>  # or run: moss init",
    )


def check_key_format() -> CheckResult:
    """Check that the project key has a valid prefix."""
    val = _resolve_value("project_key", "MOSS_PROJECT_KEY", "project_key")
    if not val:
        return CheckResult(
            category="credentials",
            name="key_format",
            status="fail",
            detail="Cannot check key format -- project key is not set.",
        )
    if re.match(r"^(pk_live_|ak_live_|moss_)", val):
        return CheckResult(
            category="credentials",
            name="key_format",
            status="pass",
            detail="Project key has a valid prefix.",
        )
    return CheckResult(
        category="credentials",
        name="key_format",
        status="warn",
        detail=f"Project key prefix '{val[:8]}' does not match pk_live_ or ak_live_.",
        fix="Verify your key at https://app.usemoss.dev/settings.",
    )


def check_credentials_valid(client: Any) -> CheckResult:
    """Try listing indexes to verify credentials work."""
    if client is None:
        return CheckResult(
            category="credentials",
            name="credentials_valid",
            status="fail",
            detail="Cannot validate credentials -- client not available.",
        )
    import asyncio

    try:
        asyncio.run(client.list_indexes())
        return CheckResult(
            category="credentials",
            name="credentials_valid",
            status="pass",
            detail="Credentials are valid (list_indexes succeeded).",
        )
    except Exception as exc:
        return CheckResult(
            category="credentials",
            name="credentials_valid",
            status="fail",
            detail=f"Credentials check failed: {exc}",
            fix="Run: moss init",
        )


# ---------------------------------------------------------------------------
# Connectivity checks
# ---------------------------------------------------------------------------

_API_HOST = "service.usemoss.dev"


def check_dns_resolution() -> CheckResult:
    """Check DNS resolution for the API host."""
    try:
        results = socket.getaddrinfo(_API_HOST, 443)
        ip = results[0][4][0] if results else "unknown"
        return CheckResult(
            category="connectivity",
            name="dns_resolution",
            status="pass",
            detail=f"DNS resolves {_API_HOST} -> {ip}.",
        )
    except socket.gaierror as exc:
        return CheckResult(
            category="connectivity",
            name="dns_resolution",
            status="fail",
            detail=f"DNS resolution failed for {_API_HOST}: {exc}",
            fix="Check your network connection and DNS settings.",
        )


def check_api_reachable() -> CheckResult:
    """HTTPS connection to the API host with a timeout; report latency.

    The API may return 404 at the root path -- that still proves the host is
    reachable and TLS works.  Only 5xx or connection failures are concerning.
    """
    url = f"https://{_API_HOST}/"
    try:
        start = time.monotonic()
        req = urllib.request.Request(url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.status
        except urllib.error.HTTPError as http_err:
            status_code = http_err.code
        latency_ms = (time.monotonic() - start) * 1000

        if status_code < 500:
            return CheckResult(
                category="connectivity",
                name="api_reachable",
                status="pass",
                detail=f"API reachable ({latency_ms:.0f}ms).",
            )
        return CheckResult(
            category="connectivity",
            name="api_reachable",
            status="warn",
            detail=f"API returned HTTP {status_code} ({latency_ms:.0f}ms).",
        )
    except Exception as exc:
        return CheckResult(
            category="connectivity",
            name="api_reachable",
            status="fail",
            detail=f"API unreachable: {exc}",
            fix="Check your network connection or firewall settings.",
        )


# ---------------------------------------------------------------------------
# Version checks
# ---------------------------------------------------------------------------


def check_cli_version() -> CheckResult:
    """Compare installed CLI version to latest on PyPI."""
    try:
        current = importlib.metadata.version("moss-cli")
    except importlib.metadata.PackageNotFoundError:
        current = "unknown"

    try:
        import json as _json

        url = "https://pypi.org/pypi/moss-cli/json"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
            latest = data["info"]["version"]
    except Exception:
        return CheckResult(
            category="sdk_versions",
            name="cli_version",
            status="warn",
            detail=f"moss-cli {current} (could not check PyPI for latest).",
        )

    if current == latest:
        return CheckResult(
            category="sdk_versions",
            name="cli_version",
            status="pass",
            detail=f"moss-cli {current} is up to date.",
        )
    return CheckResult(
        category="sdk_versions",
        name="cli_version",
        status="warn",
        detail=f"moss-cli {current} installed, latest is {latest}.",
        fix=f"pip install --upgrade moss-cli=={latest}",
    )


def check_sdk_version() -> CheckResult:
    """Report the installed moss SDK version."""
    try:
        version = importlib.metadata.version("moss")
        return CheckResult(
            category="sdk_versions",
            name="sdk_version",
            status="pass",
            detail=f"moss SDK {version}.",
        )
    except importlib.metadata.PackageNotFoundError:
        return CheckResult(
            category="sdk_versions",
            name="sdk_version",
            status="fail",
            detail="moss SDK is not installed.",
            fix="pip install moss",
        )


# ---------------------------------------------------------------------------
# Environment checks
# ---------------------------------------------------------------------------


def check_python_version() -> CheckResult:
    """Verify Python >= 3.10."""
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    if (major, minor) >= (3, 10):
        return CheckResult(
            category="environment",
            name="python_version",
            status="pass",
            detail=f"Python {version_str}.",
        )
    return CheckResult(
        category="environment",
        name="python_version",
        status="fail",
        detail=f"Python {version_str} -- 3.10+ required.",
        fix="Install Python 3.10 or newer.",
    )


def check_node_available() -> CheckResult:
    """Check if Node.js is installed and report its version."""
    node = shutil.which("node")
    if not node:
        return CheckResult(
            category="environment",
            name="node_available",
            status="warn",
            detail="Node.js not found on PATH.",
            fix="Install Node.js from https://nodejs.org/",
        )
    try:
        proc = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = proc.stdout.strip()
        return CheckResult(
            category="environment",
            name="node_available",
            status="pass",
            detail=f"Node.js {version}.",
        )
    except Exception as exc:
        return CheckResult(
            category="environment",
            name="node_available",
            status="warn",
            detail=f"Node.js found but version check failed: {exc}",
        )


def check_onnx_available() -> CheckResult:
    """Check if onnxruntime is importable."""
    try:
        ort = importlib.import_module("onnxruntime")
        version = getattr(ort, "__version__", "unknown")
        return CheckResult(
            category="environment",
            name="onnx_available",
            status="pass",
            detail=f"onnxruntime {version}.",
        )
    except ImportError:
        return CheckResult(
            category="environment",
            name="onnx_available",
            status="warn",
            detail="onnxruntime is not installed (optional, for local inference).",
            fix="pip install onnxruntime",
        )


# ---------------------------------------------------------------------------
# Index checks
# ---------------------------------------------------------------------------


def check_indexes(client: Any) -> CheckResult:
    """List indexes and flag stale ones (>30 days since updated_at)."""
    if client is None:
        return CheckResult(
            category="indexes",
            name="indexes",
            status="fail",
            detail="Cannot check indexes -- client not available.",
        )
    import asyncio

    try:
        indexes = asyncio.run(client.list_indexes())
    except Exception as exc:
        return CheckResult(
            category="indexes",
            name="indexes",
            status="fail",
            detail=f"Failed to list indexes: {exc}",
        )

    if not indexes:
        return CheckResult(
            category="indexes",
            name="indexes",
            status="warn",
            detail="No indexes found in this project.",
        )

    now = datetime.now(timezone.utc)
    stale: list[str] = []
    for idx in indexes:
        updated = getattr(idx, "updated_at", None)
        if updated and isinstance(updated, str):
            try:
                # Parse ISO 8601 timestamp
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                days = (now - dt).days
                if days > 30:
                    stale.append(f"{idx.name} ({days}d)")
            except (ValueError, TypeError):
                pass

    total = len(indexes)
    if stale:
        return CheckResult(
            category="indexes",
            name="indexes",
            status="warn",
            detail=f"{total} index(es), {len(stale)} stale: {', '.join(stale)}.",
        )
    return CheckResult(
        category="indexes",
        name="indexes",
        status="pass",
        detail=f"{total} index(es), all recently updated.",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_all_checks(client: Any = None) -> List[CheckResult]:
    """Run all diagnostic checks and return results."""
    results: List[CheckResult] = []

    # Credentials
    results.append(check_project_id_set())
    results.append(check_project_key_set())
    results.append(check_key_format())
    results.append(check_credentials_valid(client))

    # Connectivity
    results.append(check_dns_resolution())
    results.append(check_api_reachable())

    # Versions
    results.append(check_cli_version())
    results.append(check_sdk_version())

    # Environment
    results.append(check_python_version())
    results.append(check_node_available())
    results.append(check_onnx_available())

    # Indexes
    results.append(check_indexes(client))

    return results
