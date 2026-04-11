"""moss query command."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import typer
from rich.console import Console

from moss import MossClient, QueryOptions

from .. import output
from ..context import get_client, get_ctx
from ..errors import CliValidationError

console = Console()


def query_command(
    ctx: typer.Context,
    index_name: str = typer.Argument(..., help="Index name"),
    query_text: Optional[str] = typer.Argument(None, help="Search query (reads from stdin if omitted)"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
    alpha: float = typer.Option(0.8, "--alpha", "-a", help="Semantic weight (0.0=keyword, 1.0=semantic)"),
    filter_json: Optional[str] = typer.Option(None, "--filter", help="Metadata filter as JSON string"),
    cloud: bool = typer.Option(False, "--cloud", "-c", help="Query via cloud API instead of downloading the index"),
) -> None:
    """Query an index. Downloads the index and queries on-device by default. Use --cloud to skip the download and query via the cloud API."""
    cli = get_ctx(ctx)

    # Resolve query text
    if query_text is None:
        if sys.stdin.isatty():
            raise CliValidationError(
                "No query provided.",
                hint="Pass as argument or pipe via stdin.",
            )
        query_text = sys.stdin.read().strip()
        if not query_text:
            raise CliValidationError("Empty query from stdin.")

    # Parse filter
    parsed_filter = None
    if filter_json:
        try:
            parsed_filter = json.loads(filter_json)
        except json.JSONDecodeError as e:
            raise CliValidationError(
                f"Invalid --filter JSON: {e}",
                hint="Provide a valid JSON object, e.g. --filter '{\"key\": \"value\"}'",
            )

    if cloud and parsed_filter:
        raise CliValidationError(
            "Metadata filters are only supported for local queries.",
            hint="Remove --cloud or --filter.",
        )

    client = get_client(ctx)

    async def _run() -> None:
        if not cloud:
            if not cli.json_output:
                console.print(f"Loading index [cyan]{index_name}[/cyan] locally...")
            await client.load_index(index_name)

        options = QueryOptions(top_k=top_k, alpha=alpha, filter=parsed_filter)
        result = await client.query(index_name, query_text, options)
        output.print_search_results(result, json_mode=cli.json_output, envelope=cli.json_envelope, command="query")

    asyncio.run(_run())
