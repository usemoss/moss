"""moss agent-config -- output AGENTS.md snippet with project info."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console

from ..config import load_config
from ..context import get_ctx
from ..errors import CliValidationError

console = Console()

SUPPORTED_FRAMEWORKS = ["mcp", "vercel-ai-sdk", "langchain", "openai-agents", "rest"]


def _resolve_credential_soft(value: Optional[str], env_key: str, config_key: str) -> Optional[str]:
    """Resolve a credential without erroring. Returns None if unavailable."""
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
    return None


def _fetch_indexes(project_id: str, project_key: str) -> List[Dict[str, Any]]:
    """Fetch index list via SDK. Returns empty list on failure."""
    try:
        from moss import MossClient

        client = MossClient(project_id, project_key)
        indexes = asyncio.run(client.list_indexes())
        return [
            {
                "name": idx.name,
                "status": idx.status,
                "doc_count": idx.doc_count,
                "model": idx.model.id,
            }
            for idx in indexes
        ]
    except Exception:
        return []


def _framework_snippet(framework: str, project_id: str) -> str:
    """Generate framework-specific quickstart code."""
    if framework == "mcp":
        return f"""\
```bash
# Add MCP server to your agent
claude mcp add moss -- npx -y @moss-tools/mcp-server

# Or use the JSON config:
moss mcp-config --client claude
```"""

    if framework == "vercel-ai-sdk":
        return f"""\
```typescript
import {{ generateText }} from "ai";
import {{ createMossTools }} from "@moss-tools/vercel-ai";

const tools = createMossTools({{
  projectId: "{project_id}",
}});

const result = await generateText({{
  model: yourModel,
  tools,
  prompt: "Search for relevant documents",
}});
```"""

    if framework == "langchain":
        return f"""\
```python
from langchain_community.tools import MossSearchTool

tool = MossSearchTool(
    project_id="{project_id}",
)
# Add to your agent's tool list
```"""

    if framework == "openai-agents":
        return f"""\
```python
from agents import Agent, Runner
from moss_tools import moss_search_tool

agent = Agent(
    name="search-agent",
    tools=[moss_search_tool(project_id="{project_id}")],
)
```"""

    if framework == "rest":
        return f"""\
```bash
curl -X POST https://api.usemoss.dev/v1/search \\
  -H "Authorization: Bearer $MOSS_PROJECT_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{{"project_id": "{project_id}", "index": "your-index", "query": "your query"}}'
```"""

    return ""


def _build_markdown(
    project_id: str,
    indexes: List[Dict[str, Any]],
    framework: str,
    focus_index: Optional[str],
) -> str:
    """Build the AGENTS.md markdown snippet."""
    lines = [
        "# Moss Semantic Search",
        "",
        f"**Project ID:** `{project_id}`",
        "",
    ]

    if indexes:
        lines.append("## Available Indexes")
        lines.append("")
        if focus_index:
            matched = [idx for idx in indexes if idx["name"] == focus_index]
            display = matched if matched else indexes
        else:
            display = indexes
        for idx in display:
            lines.append(f"- **{idx['name']}** -- {idx['doc_count']} docs, model: `{idx['model']}`, status: {idx['status']}")
        lines.append("")
    else:
        lines.append("## Indexes")
        lines.append("")
        lines.append("No indexes found. Create one with `moss index create`.")
        lines.append("")

    lines.append(f"## Quickstart ({framework})")
    lines.append("")
    lines.append(_framework_snippet(framework, project_id))
    lines.append("")

    return "\n".join(lines)


def _build_json_output(
    project_id: str,
    indexes: List[Dict[str, Any]],
    framework: str,
    focus_index: Optional[str],
) -> Dict[str, Any]:
    """Build structured JSON output."""
    result: Dict[str, Any] = {
        "project_id": project_id,
        "framework": framework,
    }
    if focus_index:
        matched = [idx for idx in indexes if idx["name"] == focus_index]
        result["indexes"] = matched if matched else indexes
        if focus_index:
            result["focus_index"] = focus_index
    else:
        result["indexes"] = indexes

    result["quickstart"] = _framework_snippet(framework, project_id)
    return result


def agent_config_command(
    ctx: typer.Context,
    framework: str = typer.Option(
        "mcp",
        "--framework",
        "-f",
        help=f"Framework for quickstart code ({', '.join(SUPPORTED_FRAMEWORKS)})",
    ),
    index: Optional[str] = typer.Option(
        None, "--index", "-i", help="Focus on a specific index"
    ),
) -> None:
    """Output AGENTS.md snippet with project info and index details."""
    cli = get_ctx(ctx)

    if framework not in SUPPORTED_FRAMEWORKS:
        raise CliValidationError(
            f"Unsupported framework '{framework}'.",
            hint=f"Supported frameworks: {', '.join(SUPPORTED_FRAMEWORKS)}",
        )

    project_id = _resolve_credential_soft(cli.project_id, "MOSS_PROJECT_ID", "project_id")
    project_key = _resolve_credential_soft(cli.project_key, "MOSS_PROJECT_KEY", "project_key")

    # Try to fetch indexes if credentials available
    indexes: List[Dict[str, Any]] = []
    if project_id and project_key:
        indexes = _fetch_indexes(project_id, project_key)

    display_project_id = project_id or "<your-project-id>"

    if cli.json_output:
        data = _build_json_output(display_project_id, indexes, framework, index)
        print(json.dumps(data, indent=2))
    else:
        md = _build_markdown(display_project_id, indexes, framework, index)
        console.print(md)
