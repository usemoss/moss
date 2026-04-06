"""Minimal demo: register Moss as an ElevenLabs client tool.

This example shows the registration pattern without starting a full audio
conversation. For a complete voice agent demo, see ``apps/elevenlabs-moss/``.

Prerequisites:
    pip install elevenlabs-moss python-dotenv

Environment variables (or pass directly):
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME
"""

import asyncio
import os

from dotenv import load_dotenv
from elevenlabs.conversational_ai.conversation import ClientTools

from elevenlabs_moss import MossClientTool

load_dotenv()


async def main():
    """Demonstrate MossClientTool registration and a direct search call."""
    moss_tool = MossClientTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=os.getenv("MOSS_INDEX_NAME", "support-docs"),
        tool_name="search_knowledge_base",
        top_k=3,
    )

    # Load the index
    await moss_tool.load_index()

    # Register with ElevenLabs ClientTools
    client_tools = ClientTools()
    moss_tool.register(client_tools)
    print("Moss tool registered with ElevenLabs ClientTools")

    # Test a direct search
    result = await moss_tool.search("how long do refunds take?")
    print(f"\nSearch result:\n{result}")


if __name__ == "__main__":
    asyncio.run(main())
