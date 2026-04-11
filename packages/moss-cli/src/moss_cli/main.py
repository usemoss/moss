"""Main CLI entry point."""

from __future__ import annotations

import logging
import sys
from typing import Optional

import click
import typer

from .commands.agent_config import agent_config_command
from .commands.doc import doc_app
from .commands.doctor import doctor_command
from .commands.experimental import experimental_app
from .commands.index import index_app
from .commands.init_cmd import init_command
from .commands.job import job_app
from .commands.mcp_config import mcp_config_command
from .commands.migrate import migrate_app
from .commands.search import query_command
from .commands.snapshot import snapshot_app
from .commands.status import status_command
from .commands.version import version_command
from .context import CLIContext
from .errors import (
    CliError,
    CliUserAbortError,
    CliValidationError,
    normalize_exception,
)
from .output import print_cli_error

app = typer.Typer(
    name="moss",
    help="Moss Semantic Search CLI",
    add_completion=True,
    no_args_is_help=True,
)

# Register subgroups
app.add_typer(index_app, name="index", help="Manage indexes")
app.add_typer(doc_app, name="doc", help="Manage documents")
app.add_typer(job_app, name="job", help="Track background jobs")
app.add_typer(experimental_app, name="experimental", help="Experimental commands")
app.add_typer(snapshot_app, name="snapshot", help="Manage index snapshots (coming soon)")
app.add_typer(migrate_app, name="migrate", help="Migrate data from other vector DBs")

# Register top-level commands
app.command(name="query")(query_command)
app.command(name="init")(init_command)
app.command(name="version")(version_command)
app.command(name="doctor")(doctor_command)
app.command(name="status")(status_command)
app.command(name="mcp-config")(mcp_config_command)
app.command(name="agent-config")(agent_config_command)


@app.callback()
def main(
    ctx: typer.Context,
    project_id: Optional[str] = typer.Option(
        None, "--project-id", "-p", envvar="MOSS_PROJECT_ID", help="Project ID"
    ),
    project_key: Optional[str] = typer.Option(
        None, "--project-key", envvar="MOSS_PROJECT_KEY", help="Project key"
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON"
    ),
    json_envelope: bool = typer.Option(
        False,
        "--json-envelope",
        envvar="MOSS_JSON_ENVELOPE",
        help="Wrap JSON output in {ok, data, meta} envelope",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging"
    ),
    no_input: bool = typer.Option(
        False, "--yes", "-y", help="Skip all interactive prompts"
    ),
) -> None:
    """Moss Semantic Search CLI."""
    ctx.ensure_object(dict)
    ctx.obj = CLIContext(
        project_id=project_id,
        project_key=project_key,
        json_output=json_output,
        json_envelope=json_envelope,
        verbose=verbose,
        no_input=no_input,
    )

    if verbose:
        logging.basicConfig(level=logging.DEBUG)


def _is_json_mode() -> bool:
    """Detect --json from sys.argv for error rendering before ctx is set up."""
    return "--json" in sys.argv


def run() -> None:
    """Entry point for the console script."""
    try:
        app()
    except (typer.Exit, SystemExit):
        raise
    except typer.Abort:
        error = CliUserAbortError("Operation cancelled.")
        print_cli_error(error, json_mode=_is_json_mode())
        raise SystemExit(error.exit_code)
    except KeyboardInterrupt:
        error = CliUserAbortError("Interrupted.")
        print_cli_error(error, json_mode=_is_json_mode())
        raise SystemExit(error.exit_code)
    except click.BadParameter as e:
        error = CliValidationError(str(e))
        print_cli_error(error, json_mode=_is_json_mode())
        raise SystemExit(error.exit_code)
    except click.UsageError as e:
        error = CliValidationError(str(e))
        print_cli_error(error, json_mode=_is_json_mode())
        raise SystemExit(error.exit_code)
    except CliError as e:
        print_cli_error(e, json_mode=_is_json_mode())
        raise SystemExit(e.exit_code)
    except Exception as e:
        error = normalize_exception(e)
        print_cli_error(error, json_mode=_is_json_mode())
        raise SystemExit(error.exit_code)


if __name__ == "__main__":
    run()
