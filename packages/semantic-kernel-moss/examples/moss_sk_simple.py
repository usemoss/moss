"""Minimal demo: Moss semantic search with a Semantic Kernel agent."""

import asyncio
import os

import semantic_kernel as sk

from semantic_kernel_moss import MossPlugin


async def main():
    """Run a Semantic Kernel agent with Moss semantic search."""
    moss = MossPlugin(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=os.getenv("MOSS_INDEX_NAME", "my-index"),
    )
    await moss.load_index()

    kernel = sk.Kernel()
    kernel.add_plugin(moss, plugin_name="moss")

    result = await kernel.invoke(function_name="search", plugin_name="moss", query="What are your shipping options?")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
