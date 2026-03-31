"""ElevenLabs Conversational AI Bot with Moss Semantic Retrieval.

A voice AI assistant powered by ElevenLabs Conversational AI:
- Uses ElevenLabs for the full voice pipeline (STT + LLM + TTS)
- Searches a knowledge base using Moss semantic retrieval
- Registers Moss as a client tool the agent can call during conversation

Required services:
- ElevenLabs (Conversational AI agent)
- Moss (Semantic Retrieval)

Run::

    uv run elevenlabs_bot.py
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import (
    ClientTools,
    Conversation,
)
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs_moss import MossClientTool

load_dotenv(override=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("elevenlabs_bot")


async def main():
    """Run the ElevenLabs voice agent with Moss retrieval."""
    required_vars = [
        "ELEVENLABS_API_KEY",
        "ELEVENLABS_AGENT_ID",
        "MOSS_PROJECT_ID",
        "MOSS_PROJECT_KEY",
        "MOSS_INDEX_NAME",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Copy env.example to .env and fill in your credentials.")
        logger.error("  Moss credentials: https://portal.usemoss.dev")
        logger.error("  ElevenLabs API key: https://elevenlabs.io")
        return

    # Set up Moss retrieval as a client tool
    moss_tool = MossClientTool(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
        index_name=os.environ["MOSS_INDEX_NAME"],
        tool_name="search_knowledge_base",
        top_k=3,
    )

    logger.info("Loading Moss index '%s'...", os.environ["MOSS_INDEX_NAME"])
    await moss_tool.load_index()

    # Let ClientTools create its own event loop thread for async tool callbacks
    client_tools = ClientTools()
    moss_tool.register(client_tools)

    # Start the conversation
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    conversation = Conversation(
        client=client,
        agent_id=os.environ["ELEVENLABS_AGENT_ID"],
        requires_auth=False,
        audio_interface=DefaultAudioInterface(),
        client_tools=client_tools,
        callback_agent_response=lambda text: logger.info("Agent: %s", text),
        callback_user_transcript=lambda text: logger.info("User: %s", text),
    )

    logger.info("Starting conversation. Speak into your microphone. Press Ctrl+C to end.")
    conversation.start_session()

    try:
        # Offload the blocking wait to a thread so the event loop stays free
        # for async Moss tool callbacks
        await asyncio.to_thread(conversation.wait_for_session_end)
    except asyncio.CancelledError:
        pass
    finally:
        conversation.end_session()
        logger.info("Conversation ended.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
