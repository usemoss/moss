"""Poll job status with a rich progress bar."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from moss import MossClient

from . import output

console = Console()


def _status_str(status_obj: object) -> str:
    raw = status_obj.status.value if hasattr(status_obj.status, "value") else str(status_obj.status)
    return raw.upper()


def _progress_float(status_obj: object) -> float:
    p = float(status_obj.progress)
    return p / 100.0 if p > 1 else p


async def wait_for_job(
    client: MossClient,
    job_id: str,
    poll_interval: float = 2.0,
    json_mode: bool = False,
) -> None:
    """Poll job status until terminal state, showing progress."""
    terminal = {"COMPLETED", "FAILED"}

    if json_mode:
        while True:
            status = await client.get_job_status(job_id)
            status_val = _status_str(status)
            if status_val in terminal:
                output.print_job_status(status, json_mode=True)
                if status_val == "FAILED":
                    raise SystemExit(1)
                return
            await asyncio.sleep(poll_interval)

    with Live(Spinner("dots", text="Waiting for job..."), console=console, transient=True) as live:
        while True:
            status = await client.get_job_status(job_id)
            status_val = _status_str(status)

            phase = getattr(status, "current_phase", None)
            phase_str = ""
            if phase is not None:
                phase_str = f" ({phase.value if hasattr(phase, 'value') else str(phase)})"

            progress_pct = f"{_progress_float(status):.0%}"
            text = Text.from_markup(
                f"[yellow]{status_val}[/yellow] {progress_pct}{phase_str}"
            )
            live.update(Spinner("dots", text=text))

            if status_val in terminal:
                break
            await asyncio.sleep(poll_interval)

    output.print_job_status(status, json_mode=False)
    if status_val == "FAILED":
        raise SystemExit(1)
