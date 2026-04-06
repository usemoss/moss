"""Interactive CLI chatbot: Gemma + Moss retrieval-augmented generation.

Prerequisites:
    pip install gemma-moss python-dotenv
    ollama pull gemma4

Environment variables:
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from gemma_moss import GemmaMossSession, MossRetriever
from gemma_moss.session import make_ollama_query_rewriter

load_dotenv()


async def main():
    """Run the interactive chatbot."""
    # Validate environment
    required = ["MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Set them in a .env file or export them.")
        sys.exit(1)

    model = os.getenv("OLLAMA_MODEL", "gemma4")
    index_name = os.getenv("MOSS_INDEX_NAME")

    # Check Ollama is reachable
    try:
        from ollama import AsyncClient

        client = AsyncClient()
        await client.show(model)
    except Exception as e:
        print(f"Cannot reach Ollama or model '{model}' not found: {e}")
        print(f"Make sure Ollama is running and run: ollama pull {model}")
        sys.exit(1)

    # Set up retriever
    retriever = MossRetriever(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=index_name,
    )
    print(f"Loading Moss index '{index_name}'...")
    await retriever.load_index()

    # Set up session with query rewriter
    session = GemmaMossSession(
        retriever=retriever,
        model=model,
        query_rewriter=make_ollama_query_rewriter(model=model),
    )

    print(f"\nGemma + Moss Chat (model: {model}, index: {index_name})")
    print("Commands: /reset (clear history), /quit (exit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("Goodbye!")
            break
        if user_input == "/reset":
            session.reset()
            print("History cleared.\n")
            continue

        print("Assistant: ", end="", flush=True)
        async for chunk in session.ask_stream(user_input):
            print(chunk, end="", flush=True)
        print("\n")


if __name__ == "__main__":
    asyncio.run(main())
