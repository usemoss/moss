import json
import logging
import os
import time
from dotenv import load_dotenv
from livekit import rtc
from livekit.plugins import openai, deepgram, silero, cartesia
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents import (
    JobContext,
    WorkerOptions,
    cli,
    ChatContext,
    ChatMessage,
    Agent,
    AgentSession,
)


# Moss Import
from moss import MossClient, QueryOptions

load_dotenv()

# Configuration
MOSS_PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
MOSS_PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
INDEX_NAME = os.getenv("MOSS_INDEX_NAME", "demo-customer_faqs")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moss-agent")

class MossSemanticRetrievalAgent(Agent):

    def __init__(self, moss_client: MossClient, room: rtc.Room):
        super().__init__(
            instructions="""
                You are a helpful customer support voice assistant.
                You have access to a knowledge base which will be provided to you as context.
                Always answer the user's question based on the provided context.
                If the context doesn't contain the answer, politely say you don't know.
            """
        )
        self.moss = moss_client
        self.room = room

    async def _publish_retrieval(self, query: str, results, fallback_ms: float) -> None:
        """Send the retrieved chunks to the web UI over a LiveKit data channel."""
        # Use Moss's own server-reported search time; fall back to wall-clock.
        server_ms = getattr(results, "time_taken_ms", None)
        took_ms = float(server_ms) if server_ms is not None else fallback_ms
        payload = {
            "query": query,
            "docs": [
                {
                    "id": getattr(d, "id", None),
                    "text": d.text,
                    "score": float(getattr(d, "score", 0.0)),
                }
                for d in (results.docs if results and results.docs else [])
            ],
            "took_ms": round(took_ms, 2),
        }
        try:
            await self.room.local_participant.publish_data(
                json.dumps(payload).encode("utf-8"),
                reliable=True,
                topic="moss.retrieval",
            )
        except Exception as e:
            logger.warning(f"Failed to publish retrieval data: {e}")

    async def on_user_turn_completed(self, turn_ctx: ChatContext, new_message: ChatMessage) -> None:
        """
        Intercept user message -> Search Moss -> Inject Context -> Continue
        """
        user_query = new_message.text_content
        logger.info(f"User asked: {user_query}")

        try:
            # 1. Automatic Search (timed, so the UI can show how fast Moss is)
            t0 = time.perf_counter()
            results = await self.moss.query(
                INDEX_NAME,
                user_query,
                QueryOptions(top_k=5, alpha=0.8)
            )
            took_ms = (time.perf_counter() - t0) * 1000.0

            # 2. Stream the retrieval to the web UI (the Moss knowledge-base panel)
            await self._publish_retrieval(user_query, results, took_ms)

            # 3. Context Injection
            if results.docs:
                context_str = "\n".join([f"- {d.text}" for d in results.docs])
                injection = f"Relevant context from knowledge base:\n{context_str}\n\nUse this to answer the user."

                # Insert into chat history as a system message
                turn_ctx.add_message(role="system", content=injection)
                logger.info(f"Injected context ({took_ms:.1f}ms): {context_str[:100]}...")
            else:
                logger.info("No relevant context found in Moss index")

        except Exception as e:
            logger.error(f"Moss search failed: {e}", exc_info=True)

        # 3. Proceed with standard generation
        await super().on_user_turn_completed(turn_ctx, new_message)


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # Initialize Moss
    moss_client = MossClient(project_id=MOSS_PROJECT_ID, project_key=MOSS_PROJECT_KEY)
    
    # Pre-load index
    try:
        await moss_client.load_index(INDEX_NAME)
        logger.info(f"Successfully loaded index: {INDEX_NAME}")
    except Exception as e:
        logger.warning(f"Index not found or failed to load: {e}")
        logger.warning("Moss queries will fail until the index is created. Run upload.py first.")

    # Create Session
    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US"),
        llm=openai.LLM(model="gpt-4o-mini"),
        # sonic-turbo = Cartesia's lowest-latency model; "Jacqueline" voice.
        # Swap the id for any voice from play.cartesia.ai.
        tts=cartesia.TTS(model="sonic-turbo", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        # activation_threshold above the 0.5 default + a short silence window
        # cuts false triggers so the agent doesn't talk over the caller.
        vad=silero.VAD.load(min_silence_duration=0.5, activation_threshold=0.6),
        # A real turn-detection model + endpointing delays make turn-taking
        # feel crisp instead of guessing on raw VAD.
        turn_handling={
            "turn_detection": MultilingualModel(),
            "endpointing": {"min_delay": 0.5, "max_delay": 1.5},
        },
    )

    # Start the session with our custom MossSemanticRetrievalAgent
    await session.start(
        agent=MossSemanticRetrievalAgent(moss_client, ctx.room),
        room=ctx.room,
    )

    # Speak first, instantly — a fixed opener via say() skips the LLM round-trip.
    await session.say(
        "Thanks for calling Northwind support. How can I help you today?",
        allow_interruptions=True,
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))