"""Minimal demo: Moss semantic search with a Strands Agent."""

import asyncio
import os

from strands import Agent

from strands_agents_moss import MossSearchTool


async def main():
    """Run a Strands agent with Moss semantic search."""
    moss = MossSearchTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=os.getenv("MOSS_INDEX_NAME", "my-index"),
    )
    await moss.load_index()

    agent = Agent(tools=[moss.tool])
    agent("What are your shipping options?")


if __name__ == "__main__":
    asyncio.run(main())
