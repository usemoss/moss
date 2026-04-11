"""moss doc {add, delete, get} commands."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console

from moss import GetDocumentsOptions, MutationOptions

from .. import output
from ..context import get_client, get_ctx
from ..documents import load_documents
from ..errors import CliValidationError
from ..job_waiter import wait_for_job

console = Console()
doc_app = typer.Typer(name="doc", help="Manage documents in an index")


@doc_app.command(name="add")
def add(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Path to JSON/CSV document file, or '-' for stdin"),
    stdin: bool = typer.Option(False, "--stdin", help="Read documents from stdin (alias for --file -)"),
    upsert: bool = typer.Option(False, "--upsert", "-u", help="Update existing documents"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job to complete"),
    poll_interval: float = typer.Option(2.0, "--poll-interval", help="Seconds between status checks"),
) -> None:
    """Add documents to an index."""
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

    options = MutationOptions(upsert=True) if upsert else None

    if not cli.json_output:
        console.print(
            f"Adding {len(docs)} document(s) to [cyan]{index_name}[/cyan]"
            f"{' (upsert)' if upsert else ''}..."
        )

    result = asyncio.run(client.add_docs(index_name, docs, options))
    output.print_mutation_result(result, json_mode=cli.json_output, envelope=cli.json_envelope, command="doc add")

    if wait:
        asyncio.run(wait_for_job(client, result.job_id, poll_interval, cli.json_output))


@doc_app.command(name="delete")
def delete(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    ids: str = typer.Option(..., "--ids", "-i", help="Comma-separated document IDs"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Wait for job to complete"),
    poll_interval: float = typer.Option(2.0, "--poll-interval", help="Seconds between status checks"),
) -> None:
    """Delete documents from an index by ID."""
    cli = get_ctx(ctx)
    client = get_client(ctx)
    doc_ids = [i.strip() for i in ids.split(",") if i.strip()]

    if not doc_ids:
        raise CliValidationError(
            "No document IDs provided.",
            hint="Use --ids 'id1,id2,id3' to specify documents to delete.",
        )

    if not cli.json_output:
        console.print(f"Deleting {len(doc_ids)} document(s) from [cyan]{index_name}[/cyan]...")

    result = asyncio.run(client.delete_docs(index_name, doc_ids))
    output.print_mutation_result(result, json_mode=cli.json_output, envelope=cli.json_envelope, command="doc delete")

    if wait:
        asyncio.run(wait_for_job(client, result.job_id, poll_interval, cli.json_output))


@doc_app.command(name="get")
def get(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    ids: Optional[str] = typer.Option(None, "--ids", "-i", help="Comma-separated document IDs (omit for all)"),
) -> None:
    """Retrieve documents from an index."""
    cli = get_ctx(ctx)
    client = get_client(ctx)

    options = None
    if ids:
        doc_ids = [i.strip() for i in ids.split(",") if i.strip()]
        options = GetDocumentsOptions(doc_ids=doc_ids)

    docs = asyncio.run(client.get_docs(index_name, options))
    output.print_doc_table(docs, json_mode=cli.json_output, envelope=cli.json_envelope, command="doc get")
