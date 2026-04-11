"""moss snapshot {create, list, restore, delete} stub commands."""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console

from ..context import CLIContext, get_ctx

console = Console()
snapshot_app = typer.Typer(name="snapshot", help="Manage index snapshots (coming soon)")

_HUMAN_MESSAGE = (
    "Index snapshots are not yet available. This feature is coming soon. "
    "See https://docs.moss.dev/docs/roadmap for updates."
)

_JSON_PAYLOAD = {
    "ok": False,
    "error": {
        "type": "not_implemented",
        "message": "Index snapshots are not yet available.",
    },
}


def _respond(cli_ctx: CLIContext) -> None:
    """Emit the not-yet-available message in the appropriate format."""
    if cli_ctx.json_output:
        print(json.dumps(_JSON_PAYLOAD, indent=2))
    else:
        console.print(f"[yellow]{_HUMAN_MESSAGE}[/yellow]")


@snapshot_app.command(name="create")
def create(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Snapshot label"),
) -> None:
    """Create a snapshot of an index."""
    cli = get_ctx(ctx)
    _respond(cli)


@snapshot_app.command(name="list")
def list_snapshots(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
) -> None:
    """List snapshots for an index."""
    cli = get_ctx(ctx)
    _respond(cli)


@snapshot_app.command(name="restore")
def restore(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to restore"),
) -> None:
    """Restore an index from a snapshot."""
    cli = get_ctx(ctx)
    _respond(cli)


@snapshot_app.command(name="delete")
def delete(
    ctx: typer.Context,
    snapshot_id: str = typer.Argument(..., help="Snapshot ID to delete"),
) -> None:
    """Delete a snapshot."""
    cli = get_ctx(ctx)
    _respond(cli)
