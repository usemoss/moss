"""Demo: Moss semantic search with a Strands Agent."""

import asyncio
import os

from strands import Agent

from strands_agents_moss import MossSearchTool


async def main():
    """Run a Strands agent with Moss semantic search."""
    # 1. Create and pre-load the Moss search tool
    moss = MossSearchTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=os.getenv("MOSS_INDEX_NAME", "my-index"),
    )
    await moss.load_index()

    # 2. Create a Strands agent with the Moss tool
    agent = Agent(
        system_prompt=(
            "You are a helpful assistant with access to a knowledge base. "
            "Use the moss_search tool to find relevant information before answering questions."
        ),
        tools=[moss.tool],
    )

    # 3. Ask a question — the agent will call moss_search automatically
    agent("What is your refund policy?")


if __name__ == "__main__":
    asyncio.run(main())
