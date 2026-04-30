"""moss version command."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def version_command(ctx: typer.Context) -> None:
    """Print CLI and SDK version information."""
    import moss_cli

    try:
        import moss
        sdk_version = moss.__version__
    except Exception:
        sdk_version = "unavailable"

    json_mode = ctx.obj.get("json_output", False)

    if json_mode:
        import json

        print(json.dumps({"cli": moss_cli.__version__, "sdk": sdk_version}))
    else:
        console.print(f"moss-cli  {moss_cli.__version__}")
        console.print(f"moss SDK  {sdk_version}")
