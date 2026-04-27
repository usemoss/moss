"""moss profile commands."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ..config import delete_profile, get_selected_profile, list_profiles

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


@profile_app.command(name="delete")
def delete_command(
    ctx: typer.Context,
    profile: str = typer.Argument(..., help="Profile name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Delete without confirmation"),
) -> None:
    """Delete a credential profile."""
    json_mode = ctx.obj.get("json_output", False)
    selected = get_selected_profile(ctx.obj.get("profile"))

    if not force and not json_mode:
        suffix = " and switch to another profile" if profile == selected else ""
        typer.confirm(f"Delete profile '{profile}'{suffix}?", abort=True)

    deleted, new_active = delete_profile(profile)
    if not deleted:
        message = f"Profile '{profile}' not found."
        if json_mode:
            print(json.dumps({"error": message}))
        else:
            console.print(f"[red]{message}[/red]")
        raise typer.Exit(1)

    if json_mode:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "deleted_profile": profile,
                    "active_profile": new_active,
                },
                indent=2,
            )
        )
        return

    console.print(f"[green]Profile '{profile}' deleted.[/green]")
    if new_active:
        console.print(f"[dim]Active profile is now '{new_active}'.[/dim]")
    else:
        console.print("[dim]No active profile is set.[/dim]")
