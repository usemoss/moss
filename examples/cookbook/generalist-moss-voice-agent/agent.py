from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, openai, silero
from moss import MossClient, QueryOptions

load_dotenv()

logger = logging.getLogger(__name__)

PERSONAS_PATH = Path(__file__).parent / "personas.json"

BASE_VOICE_RULES = """
## Rules
- Speak in short, natural sentences — this is a voice interface, not a chat UI.
- Never read out bullet points, markdown, headers, URLs, or document IDs.
- Never repeat the user's question back to them before answering.
- Never mention searching, databases, or any internal process.
- If you cannot find the answer, say so plainly and offer to help with something else.
"""


def load_persona(persona_id: str) -> dict:
    if not PERSONAS_PATH.exists():
        raise FileNotFoundError(f"personas.json not found at {PERSONAS_PATH}")

    personas = json.loads(PERSONAS_PATH.read_text())

    if persona_id in personas:
        return personas[persona_id]

    logger.warning("Persona '%s' not found, falling back to first available", persona_id)
    if not personas:
        raise ValueError("personas.json is empty")
    return next(iter(personas.values()))


class MossVoiceAgent(Agent):
    def __init__(self, moss_client: MossClient, index_name: str, instructions: str) -> None:
        super().__init__(instructions=instructions + BASE_VOICE_RULES)
        self._moss = moss_client
        self._index_name = index_name

    @function_tool
    async def moss_search(
        self,
        query: Annotated[str, "Concise query capturing what the user wants to know."],
    ) -> str:
        """Retrieve relevant information to answer the user's question.

        Call this whenever you need factual context before responding.
        """
        try:
            result = await self._moss.query(
                self._index_name,
                query,
                QueryOptions(top_k=5, alpha=0.5),
            )
        except Exception as exc:
            logger.warning("moss_search failed: %s", exc)
            return f"Search failed: {exc}"

        if not result.docs:
            return "No relevant information found for that query."

        return "\n\n---\n\n".join(doc.text for doc in result.docs)


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    # Resolve persona from room metadata, e.g. {"persona": "troubleshooter"}
    try:
        metadata = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        metadata = {}

    persona_id = metadata.get("persona", "default")
    logger.info("Starting session with persona '%s'", persona_id)

    persona = load_persona(persona_id)
    index_name: str = persona["index_name"]
    instructions: str = persona["instructions"]

    project_id = os.environ["MOSS_PROJECT_ID"]
    project_key = os.environ["MOSS_PROJECT_KEY"]
    moss_client = MossClient(project_id, project_key)

    try:
        await moss_client.load_index(index_name)
        logger.info("Loaded index '%s' into memory", index_name)
    except Exception as exc:
        logger.warning("Could not preload index '%s', will fall back to cloud: %s", index_name, exc)

    agent = MossVoiceAgent(moss_client, index_name, instructions)

    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
    )

    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
