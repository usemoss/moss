from __future__ import annotations

import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero
from moss import MossClient, QueryOptions

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a helpful voice assistant.

At the start of every conversation, silently call list_indexes to discover \
what knowledge bases are available. Never mention this to the user.

When the user asks a question:
1. Silently pick the most relevant index based on its name and call moss_search.
2. Answer using ONLY the retrieved content. If the content does not contain
   an answer, say so honestly rather than guessing.

Never mention indexes, knowledge bases, search, or any internal mechanics to \
the user. Just answer naturally as if you already know the information.
Keep responses short and conversational — this is a voice interface.
"""


class MossVoiceAgent(Agent):
    """LiveKit voice agent that routes questions to MOSS indexes dynamically."""

    def __init__(self, moss_client: MossClient) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._moss = moss_client
        self._loaded_indexes: set[str] = set()

    @function_tool
    async def list_indexes(self) -> str:
        """List all available MOSS knowledge base indexes.

        Call this at the start of the conversation and whenever you need to
        check which knowledge bases exist before searching.
        Returns each index name and how many documents it contains.
        """
        indexes = await self._moss.list_indexes()
        if not indexes:
            return (
                "No knowledge base indexes are available yet. "
                "Run create_index.py to add one."
            )
        lines = [
            f"- {idx.name}: {idx.doc_count} docs (status: {idx.status})"
            for idx in indexes
        ]
        return "Available knowledge bases:\n" + "\n".join(lines)

    @function_tool
    async def moss_search(
        self,
        index_name: Annotated[
            str,
            "Name of the MOSS index to search, exactly as returned by list_indexes.",
        ],
        query: Annotated[
            str,
            "A concise natural-language query capturing what the user wants to know.",
        ],
    ) -> str:
        """Search a MOSS knowledge base for documents relevant to the user's question.

        Use the returned text to ground your spoken answer.
        Always search before answering — do not rely on your training data.
        """
        if index_name not in self._loaded_indexes:
            try:
                await self._moss.load_index(index_name)
                self._loaded_indexes.add(index_name)
                logger.info("Loaded index '%s' into memory", index_name)
            except Exception as exc:
                logger.warning("Could not load index '%s' locally, falling back to cloud: %s", index_name, exc)

        try:
            result = await self._moss.query(
                index_name,
                query,
                QueryOptions(top_k=5, alpha=0.5),
            )
        except Exception as exc:
            logger.warning("moss_search failed for index '%s': %s", index_name, exc)
            return f"Search failed for index '{index_name}': {exc}"

        if not result.docs:
            return f"No relevant content found in '{index_name}' for that query."

        parts: list[str] = []
        for doc in result.docs:
            parts.append(doc.text)

        return "\n\n---\n\n".join(parts)


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    project_id = os.environ["MOSS_PROJECT_ID"]
    project_key = os.environ["MOSS_PROJECT_KEY"]
    moss_client = MossClient(project_id, project_key)

    agent = MossVoiceAgent(moss_client)

    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
    )

    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
