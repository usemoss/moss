from typing import Literal

from ten_moss import MossSessionConfig


class MainControlConfig(MossSessionConfig):
    """Moss session fields (moss_*) plus greeting and moss_mode."""

    greeting: str = "Hello, I am your AI assistant."
    moss_mode: Literal["ambient", "tool"] = "ambient"
