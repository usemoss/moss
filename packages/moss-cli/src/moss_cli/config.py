"""Auth resolution: CLI flags > env vars > config file."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import typer


def get_config_path() -> Path:
    return Path.home() / ".moss" / "config.json"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def resolve_credentials(
    project_id: Optional[str] = None,
    project_key: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve credentials from flags, env vars, or config file."""
    pid = project_id or os.getenv("MOSS_PROJECT_ID")
    pkey = project_key or os.getenv("MOSS_PROJECT_KEY")

    if pid and pkey:
        return pid, pkey

    config = load_config()
    pid = pid or config.get("project_id")
    pkey = pkey or config.get("project_key")

    if not pid or not pkey:
        raise typer.BadParameter(
            "Missing credentials. Provide --project-id/--project-key, "
            "set MOSS_PROJECT_ID/MOSS_PROJECT_KEY env vars, "
            "or run 'moss init' to save them."
        )
    return pid, pkey
