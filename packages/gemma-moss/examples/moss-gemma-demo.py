"""Interactive CLI chatbot: Gemma + Moss via tool calling.

Gemma decides when to search the Moss knowledge base using Ollama's
native tool-calling API.

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

load_dotenv()


async def main():
    """Run the interactive chatbot."""
    required = ["MOSS_PROJECT_ID", "MOSS_PROJECT_KEY", "MOSS_INDEX_NAME"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
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

    # Set up session — Gemma decides when to search
    session = GemmaMossSession(
        retriever=retriever,
        model=model,
        index_description=os.getenv(
            "MOSS_INDEX_DESCRIPTION", "a customer FAQ knowledge base"
        ),
    )

    print(f"\nGemma + Moss Chat (model: {model}, index: {index_name})")
    print("Gemma will search the knowledge base when it needs to.")
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

        response = await session.ask(user_input)
        print(f"Assistant: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
