"""moss version command."""

from __future__ import annotations

import typer
from rich.console import Console

from ..context import get_ctx

console = Console()


def version_command(ctx: typer.Context) -> None:
    """Print CLI and SDK version information."""
    import moss
    import moss_cli

    cli = get_ctx(ctx)

    if cli.json_output:
        import json
        import sys

        data = {
            "cli": moss_cli.__version__,
            "sdk": moss.__version__,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
        if cli.json_envelope:
            from ..output import _print_json
            _print_json(data, envelope=True, command="version")
        else:
            print(json.dumps(data))
    else:
        import sys

        console.print(f"moss-cli  {moss_cli.__version__}")
        console.print(f"moss SDK  {moss.__version__}")
        console.print(f"Python   {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
