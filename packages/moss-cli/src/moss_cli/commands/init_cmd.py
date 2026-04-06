"""moss init — interactive credential setup."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.prompt import Prompt

from moss import MossClient

from ..config import get_config_path, load_config, save_config

console = Console()


def init_command(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """Save project credentials to ~/.moss/config.json."""
    path = get_config_path()
    if path.exists() and not force:
        existing = load_config()
        if existing.get("project_id"):
            console.print(f"[yellow]Config already exists at {path}[/yellow]")
            console.print(f"  Project ID: {existing['project_id'][:8]}...")
            overwrite = Prompt.ask("Overwrite?", choices=["y", "n"], default="n")
            if overwrite != "y":
                raise typer.Abort()

    project_id = Prompt.ask("Project ID")
    project_key = Prompt.ask("Project Key", password=True)

    if not project_id or not project_key:
        console.print("[red]Both project ID and key are required.[/red]")
        raise typer.Exit(1)

    # Test credentials
    console.print("[dim]Validating credentials...[/dim]")
    try:
        client = MossClient(project_id, project_key)
        indexes = asyncio.run(client.list_indexes())
        console.print(f"[green]Authenticated. Found {len(indexes)} index(es).[/green]")
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        save_anyway = Prompt.ask("Save anyway?", choices=["y", "n"], default="n")
        if save_anyway != "y":
            raise typer.Exit(1)

    save_config({"project_id": project_id, "project_key": project_key})
    console.print(f"[green]Config saved to {path}[/green]")
