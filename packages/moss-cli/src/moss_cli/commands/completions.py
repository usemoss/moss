"""moss completions command — output shell completion scripts."""

from __future__ import annotations

from enum import Enum

import typer

from .. import output

PROG_NAME = "moss"


class Shell(str, Enum):
    bash = "bash"
    zsh = "zsh"


def completions_command(
    ctx: typer.Context,
    shell: Shell = typer.Argument(
        ..., help="Shell to generate the completion script for."
    ),
) -> None:
    """Output a shell completion script for Bash or Zsh.

    Tab-completion covers commands, subcommands, global flags, and index names.

    Bash:

        moss completions bash >> ~/.bashrc

    Zsh:

        moss completions zsh >> ~/.zshrc

    Then restart your shell (or 'source' the file) to activate it.
    """
    json_mode = ctx.obj.get("json_output", False) if ctx.obj else False

    try:
        # Prefer a public API when available.
        from typer.main import get_completion_script  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        try:
            from typer._completion_shared import get_completion_script  # type: ignore
        except Exception:  # pragma: no cover - depends on Typer installation
            output.print_error(
                "Shell completion is unavailable in this Typer installation.",
                json_mode,
            )
            raise typer.Exit(1)

    complete_var = "_{}_COMPLETE".format(PROG_NAME.replace("-", "_").upper())
    script = get_completion_script(
        prog_name=PROG_NAME, complete_var=complete_var, shell=shell.value
    )
    # Emit the raw script with no Rich markup so it can be piped or redirected
    # to a file verbatim.
    typer.echo(script)
