"""moss experimental -- experimental command group."""

from __future__ import annotations

import typer

from .keys import keys_app
from .provision import provision_command

experimental_app = typer.Typer(
    name="experimental",
    help="Experimental commands (subject to change)",
    no_args_is_help=True,
)

# Register subgroups and commands
experimental_app.add_typer(keys_app, name="keys", help="Manage agent keys")
experimental_app.command(name="provision")(provision_command)
