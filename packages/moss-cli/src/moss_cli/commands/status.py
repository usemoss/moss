"""moss status -- quick one-liner project health check."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from ..context import get_client, get_ctx
from ..errors import CliSdkError

console = Console()


def status_command(ctx: typer.Context) -> None:
    """Show a quick project status summary."""
    cli = get_ctx(ctx)
    client = get_client(ctx)

    try:
        indexes = asyncio.run(client.list_indexes())
    except Exception as exc:
        raise CliSdkError(
            f"Failed to fetch indexes: {exc}",
            hint="Check credentials with 'moss doctor'.",
        ) from exc

    total = len(indexes)
    healthy = sum(
        1 for idx in indexes if getattr(idx, "status", "").lower() in ("ready", "active")
    )

    pid = cli.project_id
    if not pid:
        import os

        from ..config import load_config

        pid = os.environ.get("MOSS_PROJECT_ID") or load_config().get("project_id", "unknown")

    if cli.json_output:
        payload = {
            "ok": True,
            "data": {
                "project_id": pid,
                "indexes": total,
                "indexes_healthy": healthy,
            },
        }
        print(json.dumps(payload, indent=2, default=str))
    else:
        health_label = "all healthy" if healthy == total else f"{healthy}/{total} healthy"
        console.print(f"{pid} | {total} indexes | {health_label}")
