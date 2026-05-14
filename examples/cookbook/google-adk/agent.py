"""ADK agent definition for the Moss cookbook.

Run with ``adk run .`` or ``adk web`` from this directory. The Live (BIDI)
voice mode uses the same agent definition; swap the model to a Live-capable
variant (e.g. ``gemini-2.5-flash-native-audio-preview-12-2025``) to try it.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from moss_adk import MossSearchTool

load_dotenv()

_moss = MossSearchTool(index_name=os.getenv("MOSS_INDEX_NAME", "moss-adk-demo-index"))

root_agent = Agent(
    name="moss_support_agent",
    model=os.getenv("ADK_MODEL", "gemini-2.5-flash"),
    description="Customer support agent backed by Moss semantic search.",
    instruction=(
        "You are a customer support assistant. Use the `moss_search` tool to "
        "look up answers in the knowledge base before responding. Quote the "
        "result faithfully and keep your reply concise."
    ),
    tools=[_moss.search_tool],
)
