"""moss experimental keys -- stub for agent key management."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ..context import get_ctx

console = Console()

keys_app = typer.Typer(
    name="keys",
    help="Manage agent keys (not yet available)",
    no_args_is_help=True,
)

_MESSAGE = "Agent key management is not yet available on your plan."


def _stub_command(ctx: typer.Context) -> None:
    """Output the unavailable message in the appropriate format."""
    cli = get_ctx(ctx)

    if cli.json_output:
        print(json.dumps({
            "status": "unavailable",
            "message": _MESSAGE,
        }, indent=2))
    else:
        console.print(f"[yellow]{_MESSAGE}[/yellow]")


@keys_app.command(name="create")
def create_key(ctx: typer.Context) -> None:
    """Create a new agent key (not yet available)."""
    _stub_command(ctx)


@keys_app.command(name="list")
def list_keys(ctx: typer.Context) -> None:
    """List agent keys (not yet available)."""
    _stub_command(ctx)


@keys_app.command(name="revoke")
def revoke_key(ctx: typer.Context) -> None:
    """Revoke an agent key (not yet available)."""
    _stub_command(ctx)


@keys_app.command(name="rotate")
def rotate_key(ctx: typer.Context) -> None:
    """Rotate an agent key (not yet available)."""
    _stub_command(ctx)
