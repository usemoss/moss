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
from ..config import resolve_credentials

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
    json_mode = ctx.obj.get("json_output", False)

    # Resolve query text
    if query_text is None:
        if sys.stdin.isatty():
            output.print_error("No query provided. Pass as argument or pipe via stdin.", json_mode)
            raise typer.Exit(1)
        query_text = sys.stdin.read().strip()
        if not query_text:
            output.print_error("Empty query from stdin.", json_mode)
            raise typer.Exit(1)

    # Parse filter
    parsed_filter = None
    if filter_json:
        try:
            parsed_filter = json.loads(filter_json)
        except json.JSONDecodeError as e:
            output.print_error(f"Invalid --filter JSON: {e}", json_mode)
            raise typer.Exit(1)

    pid, pkey = resolve_credentials(
        ctx.obj.get("project_id"), ctx.obj.get("project_key")
    )
    if cloud and parsed_filter:
        output.print_error(
            "Metadata filters are only supported for local queries. Remove --cloud or --filter.",
            json_mode,
        )
        raise typer.Exit(1)

    client = MossClient(pid, pkey)

    async def _run() -> None:
        if not cloud:
            if not json_mode:
                console.print(f"Loading index [cyan]{index_name}[/cyan] locally...")
            await client.load_index(index_name)

        options = QueryOptions(top_k=top_k, alpha=alpha, filter=parsed_filter)
        result = await client.query(index_name, query_text, options)
        output.print_search_results(result, json_mode=json_mode)

    asyncio.run(_run())
