"""Typed CLI context and client factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import typer

from moss import MossClient

from .config import resolve_credentials


@dataclass(slots=True)
class CLIContext:
    """Typed context object shared across all commands."""

    project_id: Optional[str] = None
    project_key: Optional[str] = None
    json_output: bool = False
    json_envelope: bool = False
    verbose: bool = False
    no_input: bool = False


def get_ctx(ctx: typer.Context) -> CLIContext:
    """Extract the typed CLIContext from a Typer context."""
    obj = ctx.obj
    if isinstance(obj, CLIContext):
        return obj
    raise RuntimeError("CLIContext was not initialized. This is a bug in moss-cli.")


def get_client(ctx: typer.Context) -> MossClient:
    """Create a MossClient with lazy credential resolution."""
    cli = get_ctx(ctx)
    pid, pkey = resolve_credentials(cli.project_id, cli.project_key)
    return MossClient(pid, pkey)
