from ten_moss import MossSessionConfig


class MainControlConfig(MossSessionConfig):
    """Main control config: Moss session fields (moss_*) plus the agent greeting."""

    greeting: str = "Hello, I am your AI assistant."
