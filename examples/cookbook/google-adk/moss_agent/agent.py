"""ADK voice agent definition for the Moss cookbook.

Run ``adk web`` from the cookbook directory (one level up from this file).
The agent appears in the picker as ``moss_agent``. Click the microphone to
start a voice call.
"""

import logging
import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from .moss_search import make_moss_search

load_dotenv()

# ADK's base_llm_flow logs a session-resumption handle every ~300 ms during
# a live session. That spams the terminal. Suppress INFO from that module.
logging.getLogger("google.adk.flows.llm_flows.base_llm_flow").setLevel(
    logging.WARNING
)

# moss_search lazy-loads on first call. adk web runs inside an event loop,
# so we can't do an eager `asyncio.run(load_index())` here.
_load_index, moss_search = make_moss_search(
    index_name=os.getenv("MOSS_INDEX_NAME", "moss-adk-demo-index"),
)

root_agent = Agent(
    name="moss_support_agent",
    model=os.getenv("ADK_MODEL", "gemini-3.1-flash-live-preview"),
    description="Voice customer support agent backed by Moss semantic search.",
    instruction=(
        "You are a friendly support assistant on a voice call. Before "
        "answering questions about orders, refunds, shipping, or support, "
        "call the `moss_search` tool with the user's question. Keep answers "
        "short and conversational."
    ),
    tools=[moss_search],
)
