from ten_moss import MossSessionConfig


class MainControlConfig(MossSessionConfig):
    """Main control config: Moss session fields (moss_*) plus the agent greeting."""

    greeting: str = "Hello, I am your AI assistant."
    # Speed showcase: >0 adds an artificial delay before retrieval to imitate a
    # remote vector-DB round trip, so the latency Moss saves is audible. 0 = off.
    moss_simulate_remote_ms: int = 0
