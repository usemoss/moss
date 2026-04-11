"""moss mcp-config -- generate MCP configuration for various clients."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console

from ..config import load_config
from ..context import get_ctx
from ..errors import CliValidationError

console = Console()

SUPPORTED_CLIENTS = ["claude", "claude-code", "cursor", "vscode", "windsurf", "other"]

# Clients that use JSON configuration files
_JSON_CONFIG_CLIENTS = {"claude", "cursor", "vscode", "windsurf", "other"}


def _resolve_credential(value: Optional[str], env_key: str, config_key: str) -> str:
    """Resolve a credential from CLI context, env, or config -- never error."""
    import os

    if value:
        return value
    env_val = os.getenv(env_key)
    if env_val:
        return env_val
    config = load_config()
    config_val = config.get(config_key)
    if config_val:
        return config_val
    return f"<your-{config_key.replace('_', '-')}>"


def _build_json_config(
    project_id: str,
    project_key: str,
    index: Optional[str],
) -> dict:
    """Build the mcpServers JSON config dict."""
    env: dict[str, str] = {
        "MOSS_PROJECT_ID": project_id,
        "MOSS_PROJECT_KEY": project_key,
    }
    if index:
        env["MOSS_DEFAULT_INDEX"] = index

    return {
        "mcpServers": {
            "moss": {
                "command": "npx",
                "args": ["-y", "@moss-tools/mcp-server"],
                "env": env,
            }
        }
    }


def _build_claude_code_text(index: Optional[str]) -> str:
    """Build the claude-code CLI instruction text."""
    base = "claude mcp add moss -- npx -y @moss-tools/mcp-server"
    lines = [base]
    if index:
        lines.append("")
        lines.append(f"Then set MOSS_DEFAULT_INDEX={index} in your environment.")
    return "\n".join(lines)


def _copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    system = platform.system()
    try:
        if system == "Darwin":
            proc = subprocess.run(
                ["pbcopy"],
                input=text.encode(),
                check=True,
                capture_output=True,
            )
            return proc.returncode == 0
        elif system == "Linux":
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text.encode(),
                check=True,
                capture_output=True,
            )
            return proc.returncode == 0
        elif system == "Windows":
            proc = subprocess.run(
                ["clip"],
                input=text.encode(),
                check=True,
                capture_output=True,
            )
            return proc.returncode == 0
        return False
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def mcp_config_command(
    ctx: typer.Context,
    client: str = typer.Option(
        "claude",
        "--client",
        "-c",
        help=f"Target client ({', '.join(SUPPORTED_CLIENTS)})",
    ),
    index: Optional[str] = typer.Option(
        None, "--index", "-i", help="Add MOSS_DEFAULT_INDEX to env"
    ),
    copy: bool = typer.Option(
        False, "--copy", help="Copy output to clipboard"
    ),
) -> None:
    """Generate MCP configuration for a specific client."""
    cli = get_ctx(ctx)

    if client not in SUPPORTED_CLIENTS:
        raise CliValidationError(
            f"Unsupported client '{client}'.",
            hint=f"Supported clients: {', '.join(SUPPORTED_CLIENTS)}",
        )

    project_id = _resolve_credential(cli.project_id, "MOSS_PROJECT_ID", "project_id")
    project_key = _resolve_credential(cli.project_key, "MOSS_PROJECT_KEY", "project_key")

    if client == "claude-code":
        output_text = _build_claude_code_text(index)
        if cli.json_output:
            payload = {"client": client, "instructions": output_text}
            if index:
                payload["index"] = index
            print(json.dumps(payload, indent=2))
        else:
            console.print(output_text)
    else:
        config = _build_json_config(project_id, project_key, index)
        output_text = json.dumps(config, indent=2)
        if cli.json_output:
            # In json mode, wrap with metadata
            payload = {"client": client, "config": config}
            if index:
                payload["index"] = index
            print(json.dumps(payload, indent=2))
        else:
            console.print(output_text)

    if copy:
        if _copy_to_clipboard(output_text):
            if not cli.json_output:
                console.print("[green]Copied to clipboard.[/green]")
        else:
            if not cli.json_output:
                console.print("[yellow]Could not copy to clipboard.[/yellow]")
