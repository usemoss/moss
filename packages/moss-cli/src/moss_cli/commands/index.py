"""moss index {create, list, get, delete} commands."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console

from .. import output
from ..context import get_client, get_ctx
from ..documents import load_documents
from ..errors import CliSdkError, CliValidationError
from ..job_waiter import wait_for_job

console = Console()
index_app = typer.Typer(name="index", help="Manage indexes")


@index_app.command(name="create")
def create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Index name"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to JSON/CSV document file, or '-' for stdin"),
    stdin: bool = typer.Option(False, "--stdin", help="Read documents from stdin (alias for --file -)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model ID (default: moss-minilm)"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job to complete"),
    poll_interval: float = typer.Option(2.0, "--poll-interval", help="Seconds between status checks"),
) -> None:
    """Create a new index with documents."""
    cli = get_ctx(ctx)
    client = get_client(ctx)

    if stdin and file:
        raise CliValidationError(
            "Cannot use both --stdin and --file.",
            hint="Use one or the other.",
        )
    if stdin:
        file = "-"
    if not file:
        raise CliValidationError(
            "One of --file or --stdin is required.",
            hint="Provide a file path with --file or pipe data via --stdin.",
        )

    docs = load_documents(file)

    if not cli.json_output:
        console.print(f"Creating index [cyan]{name}[/cyan] with {len(docs)} document(s)...")

    result = asyncio.run(client.create_index(name, docs, model))
    output.print_mutation_result(result, json_mode=cli.json_output, envelope=cli.json_envelope, command="index create")

    if wait:
        asyncio.run(wait_for_job(client, result.job_id, poll_interval, cli.json_output))


@index_app.command(name="list")
def list_indexes(ctx: typer.Context) -> None:
    """List all indexes."""
    cli = get_ctx(ctx)
    client = get_client(ctx)
    indexes = asyncio.run(client.list_indexes())
    output.print_index_table(indexes, json_mode=cli.json_output, envelope=cli.json_envelope, command="index list")


@index_app.command(name="get")
def get(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Index name"),
) -> None:
    """Get details of an index."""
    cli = get_ctx(ctx)
    client = get_client(ctx)
    info = asyncio.run(client.get_index(name))
    output.print_index_detail(info, json_mode=cli.json_output, envelope=cli.json_envelope, command="index get")


@index_app.command(name="delete")
def delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Index name"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation"),
) -> None:
    """Delete an index."""
    cli = get_ctx(ctx)
    if not confirm and not cli.no_input and not cli.json_output:
        typer.confirm(f"Delete index '{name}'?", abort=True)

    client = get_client(ctx)
    result = asyncio.run(client.delete_index(name))

    if result:
        output.print_success(f"Index '{name}' deleted.", json_mode=cli.json_output, envelope=cli.json_envelope, command="index delete")
    else:
        raise CliSdkError(
            f"Failed to delete index '{name}'.",
            hint="Check that the index exists with 'moss index list'.",
        )
