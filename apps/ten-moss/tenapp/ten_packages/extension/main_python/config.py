from typing import Literal

from ten_moss import MossSessionConfig


class MainControlConfig(MossSessionConfig):
    greeting: str = "Hello, I am your AI assistant."
    moss_mode: Literal["ambient", "tool"] = "ambient"
