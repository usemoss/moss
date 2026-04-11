"""moss doctor -- run diagnostic checks and report results."""

from __future__ import annotations

import json

import typer
from rich.console import Console

from ..checks import CheckResult, run_all_checks
from ..context import get_client, get_ctx

console = Console()
err_console = Console(stderr=True)

_STATUS_STYLE = {
    "pass": "[green][PASS][/green]",
    "warn": "[yellow][WARN][/yellow]",
    "fail": "[red][FAIL][/red]",
}


def _print_human(results: list[CheckResult], show_fix: bool) -> None:
    """Render check results as colored Rich output."""
    current_category = ""
    for r in results:
        if r.category != current_category:
            current_category = r.category
            console.print(f"\n[bold]{current_category.replace('_', ' ').title()}[/bold]")
        badge = _STATUS_STYLE.get(r.status, r.status)
        console.print(f"  {badge} {r.detail}")
        if show_fix and r.fix:
            console.print(f"         [dim]Fix: {r.fix}[/dim]")

    # Summary
    pass_count = sum(1 for r in results if r.status == "pass")
    warn_count = sum(1 for r in results if r.status == "warn")
    fail_count = sum(1 for r in results if r.status == "fail")
    console.print()
    console.print(
        f"[green]{pass_count} passed[/green], "
        f"[yellow]{warn_count} warnings[/yellow], "
        f"[red]{fail_count} failures[/red]"
    )


def _print_json(results: list[CheckResult]) -> None:
    """Render check results as JSON."""
    pass_count = sum(1 for r in results if r.status == "pass")
    warn_count = sum(1 for r in results if r.status == "warn")
    fail_count = sum(1 for r in results if r.status == "fail")
    ok = fail_count == 0
    payload = {
        "ok": ok,
        "data": {
            "checks": [r.to_dict() for r in results],
            "summary": {
                "pass": pass_count,
                "warn": warn_count,
                "fail": fail_count,
            },
        },
    }
    print(json.dumps(payload, indent=2, default=str))


def doctor_command(
    ctx: typer.Context,
    fix: bool = typer.Option(False, "--fix", help="Show suggested fix commands"),
) -> None:
    """Run diagnostic checks and report results."""
    cli = get_ctx(ctx)

    # Try to build a client; if credentials are missing, pass None
    client = None
    try:
        client = get_client(ctx)
    except Exception:
        pass

    results = run_all_checks(client)

    if cli.json_output:
        _print_json(results)
    else:
        _print_human(results, show_fix=fix)

    # Exit with non-zero if any failures
    fail_count = sum(1 for r in results if r.status == "fail")
    if fail_count > 0:
        raise typer.Exit(code=1)
