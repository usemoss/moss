#
# Community demo: Shoplabs-style ecommerce voice support bot with Moss retrieval.
#

import os

from dotenv import load_dotenv
from loguru import logger
from pipecat.frames.frames import LLMMessagesAppendFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIObserverParams, RTVIProcessor
from pipecat.runner.run import main as runner_main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat_moss import MossRetrievalService

load_dotenv(override=True)


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    """Run the ecommerce support voice bot pipeline."""
    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
    cartesia_api_key = os.getenv("CARTESIA_API_KEY")
    google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    moss_project_id = os.getenv("MOSS_PROJECT_ID")
    moss_project_key = os.getenv("MOSS_PROJECT_KEY")
    moss_index_name = os.getenv("MOSS_INDEX_NAME")

    assert deepgram_api_key is not None
    assert cartesia_api_key is not None
    assert google_api_key is not None
    assert moss_project_id is not None
    assert moss_project_key is not None
    assert moss_index_name is not None

    stt = DeepgramSTTService(api_key=deepgram_api_key)
    tts = CartesiaTTSService(
        api_key=cartesia_api_key,
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",
    )
    llm = OpenAILLMService(
        api_key=google_api_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        base_url=os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai",
        ),
    )

    moss_service = MossRetrievalService(
        project_id=moss_project_id,
        project_key=moss_project_key,
        system_prompt="Relevant ecommerce knowledge base results:\n\n",
    )

    await moss_service.load_index(moss_index_name)

    system_prompt = """You are an ecommerce voice support assistant for ShopLabs Demo Store.

You help customers with:
- refunds and returns
- shipping questions
- tracking orders
- account help
- product recommendations
- checkout and abandoned cart questions

Guidelines:
- Be concise and conversational because this is a voice interface.
- Prefer retrieved knowledge base facts over guessing.
- If the knowledge base does not answer the question, say so clearly.
- When recommending products, explain why the suggestion fits the user's need.
- When the conversation begins, warmly greet the customer and ask how you can help with products, shipping, refunds, or orders.
"""

    messages = [{"role": "system", "content": system_prompt}]
    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)
    rtvi = RTVIProcessor()
    top_k = int(os.getenv("MOSS_TOP_K", "5"))

    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            stt,
            context_aggregator.user(),
            moss_service.query(moss_index_name, top_k=top_k),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=True,
        ),
        observers=[RTVIObserver(rtvi, params=RTVIObserverParams())],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Customer connected to ShopLabs demo store")
        logger.info("Sending greeting trigger to LLM...")
        await task.queue_frames(
            [LLMMessagesAppendFrame(messages=[{"role": "user", "content": "Hello"}], run_llm=True)]
        )
        logger.info("Greeting frame queued")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Customer disconnected from ShopLabs demo store")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)


async def bot(runner_args: RunnerArguments) -> None:
    """Main bot entry point."""
    required_vars = {
        "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
        "CARTESIA_API_KEY": os.getenv("CARTESIA_API_KEY"),
        "GOOGLE_API_KEY or GEMINI_API_KEY": os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY"),
        "MOSS_PROJECT_ID": os.getenv("MOSS_PROJECT_ID"),
        "MOSS_PROJECT_KEY": os.getenv("MOSS_PROJECT_KEY"),
        "MOSS_INDEX_NAME": os.getenv("MOSS_INDEX_NAME"),
    }
    missing_vars = [name for name, value in required_vars.items() if not value]
    if missing_vars:
        logger.error("Missing required environment variables:")
        for name in missing_vars:
            logger.error("  - {}", name)
        return

    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    runner_main()
