"""moss profile commands."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ..config import get_selected_profile, list_profiles

console = Console()
profile_app = typer.Typer(name="profile", help="Manage auth profiles")


@profile_app.command(name="list")
def list_command(ctx: typer.Context) -> None:
    """List available credential profiles."""
    json_mode = ctx.obj.get("json_output", False)
    selected = get_selected_profile(ctx.obj.get("profile"))
    profiles = list_profiles()

    if json_mode:
        print(
            json.dumps(
                {
                    "active_profile": selected,
                    "profiles": profiles,
                },
                indent=2,
            )
        )
        return

    if not profiles:
        console.print("[dim]No profiles configured. Run 'moss init' first.[/dim]")
        return

    console.print("[bold]Profiles[/bold]")
    for profile in profiles:
        marker = "*" if profile == selected else " "
        console.print(f"{marker} {profile}")
