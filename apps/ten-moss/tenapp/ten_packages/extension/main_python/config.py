from typing import Literal

from ten_moss import MossSessionConfig

MOSS_MODE_AMBIENT = "ambient"
MOSS_MODE_TOOL = "tool"


def moss_mode_prepends_on_asr(moss_mode: str) -> bool:
    """Ambient prepends Moss grounding on ASR-final. Tool mode does not."""
    return moss_mode != MOSS_MODE_TOOL


class MainControlConfig(MossSessionConfig):
    """Main control config: Moss session fields (moss_*) plus the agent greeting."""

    greeting: str = "Hello, I am your AI assistant."
    # ambient (default): search on every ASR-final and prepend.
    # tool: register search_knowledge_base; the LLM decides when to search.
    moss_mode: Literal["ambient", "tool"] = MOSS_MODE_AMBIENT
