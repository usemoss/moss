"""moss job status command."""

from __future__ import annotations

import asyncio

import typer

from .. import output
from ..context import get_client, get_ctx
from ..job_waiter import wait_for_job

job_app = typer.Typer(name="job", help="Track background jobs")


@job_app.command(name="status")
def status(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Job ID"),
    wait: bool = typer.Option(False, "--wait", "-w", help="Poll until job completes"),
    poll_interval: float = typer.Option(2.0, "--poll-interval", help="Seconds between status checks"),
) -> None:
    """Get the status of a background job."""
    cli = get_ctx(ctx)
    client = get_client(ctx)

    if wait:
        asyncio.run(wait_for_job(client, job_id, poll_interval, cli.json_output))
    else:
        result = asyncio.run(client.get_job_status(job_id))
        output.print_job_status(result, json_mode=cli.json_output, envelope=cli.json_envelope, command="job status")
