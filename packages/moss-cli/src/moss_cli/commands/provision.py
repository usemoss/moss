"""moss experimental provision -- stub for project provisioning."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ..context import get_ctx

console = Console()

_MESSAGE = "Project provisioning is not yet available. Visit https://portal.usemoss.dev to create a project."


def provision_command(ctx: typer.Context) -> None:
    """Provision a new project (not yet available)."""
    cli = get_ctx(ctx)

    if cli.json_output:
        print(json.dumps({
            "status": "unavailable",
            "message": _MESSAGE,
        }, indent=2))
    else:
        console.print(f"[yellow]{_MESSAGE}[/yellow]")
