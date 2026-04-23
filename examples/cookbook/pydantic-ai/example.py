from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from moss import MossClient
from pydantic_ai import Agent

from moss_pydantic_ai import MossSearchTool


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def main() -> None:
    """Run the cookbook example using the Moss-backed search tool."""
    load_dotenv()

    client = MossClient(
        _require_env("MOSS_PROJECT_ID"),
        _require_env("MOSS_PROJECT_KEY"),
    )
    moss = MossSearchTool(
        client=client,
        index_name=_require_env("MOSS_INDEX_NAME"),
    )
    await moss.load_index()

    agent = Agent(
        _require_env("PYDANTIC_AI_MODEL"),
        system_prompt=(
            "Answer user questions with the help of Moss search when "
            "factual lookup from the knowledge base is needed."
        ),
        tools=[moss.tool],
    )

    question = os.getenv(
        "PYDANTIC_AI_PROMPT",
        "How to reset password?",
    )
    result = await agent.run(question)
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
