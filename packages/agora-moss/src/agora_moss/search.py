"""Moss + Agora Conversational AI integration.

Exposes Moss semantic search as an MCP tool over streamable HTTP, suitable
for use as an ``llm.mcp_servers`` entry in Agora ConvoAI's REST ``join`` body.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class MossAgoraSearch:
    """Moss search adapter exposed as an MCP tool."""

    @staticmethod
    def _format_results(documents: Sequence[Any]) -> list[dict[str, Any]]:
        """Format Moss ``DocumentInfo`` objects as a list of serializable dicts.

        Each doc becomes ``{"content": doc.text, "similarity": doc.score}``.
        """
        return [{"content": doc.text, "similarity": doc.score} for doc in documents]
