"""moss init -- interactive credential setup."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.prompt import Prompt

from moss import MossClient

from ..config import get_config_path, load_config, save_config
from ..context import get_ctx
from ..errors import CliValidationError

console = Console()


def init_command(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """Save project credentials to ~/.moss/config.json."""
    cli = get_ctx(ctx)
    path = get_config_path()

    # JSON mode requires --yes since init is interactive
    if cli.json_output and not cli.no_input:
        raise CliValidationError(
            "JSON mode requires --yes for non-interactive init.",
            hint="Use: moss --json --yes --project-id X --project-key Y init",
        )

    # Non-interactive mode: require credentials from flags/env
    if cli.no_input:
        if not cli.project_id or not cli.project_key:
            raise CliValidationError(
                "Non-interactive init requires --project-id and --project-key.",
                hint="Provide credentials via flags or MOSS_PROJECT_ID/MOSS_PROJECT_KEY env vars.",
            )
        save_config({"project_id": cli.project_id, "project_key": cli.project_key})
        if cli.json_output:
            import json
            data = {"status": "ok", "config_path": str(path)}
            if cli.json_envelope:
                from ..output import _print_json
                _print_json(data, envelope=True, command="init")
            else:
                print(json.dumps(data))
        else:
            console.print(f"[green]Config saved to {path}[/green]")
        return

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
        raise CliValidationError("Both project ID and key are required.")

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
