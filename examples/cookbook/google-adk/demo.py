"""Programmatic ADK + Moss demo.

Seeds a small Moss index (if missing), builds an ADK agent with the Moss
search tool, and asks one question. Useful as a smoke test.

Run::

    python demo.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from moss import DocumentInfo, MossClient

from moss_adk import MossSearchTool

APP_NAME = "moss_adk_demo"
USER_ID = "demo_user"

SEED_DOCS = [
    DocumentInfo(id="1", text="Refunds are processed within 3-5 business days of the request."),
    DocumentInfo(id="2", text="You can track your order in the dashboard under 'My Orders'."),
    DocumentInfo(id="3", text="We offer 24/7 live chat support through the help widget."),
    DocumentInfo(id="4", text="Free shipping on orders over $50 in the contiguous US."),
    DocumentInfo(id="5", text="Returns are accepted within 30 days of purchase with original packaging."),
]


async def seed_index_if_needed(client: MossClient, index_name: str) -> None:
    """Try to load the index; if it doesn't exist, create it from SEED_DOCS."""
    try:
        await client.load_index(index_name)
        print(f"Index '{index_name}' already exists; skipping seed.")
    except Exception:
        print(f"Creating index '{index_name}' with {len(SEED_DOCS)} docs...")
        await client.create_index(index_name, SEED_DOCS)
        await client.load_index(index_name)


async def main() -> None:
    load_dotenv()

    if not os.getenv("MOSS_PROJECT_ID") or not os.getenv("MOSS_PROJECT_KEY"):
        sys.exit("Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env first.")
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit(
            "Set GOOGLE_API_KEY in .env "
            "(get one at https://aistudio.google.com/app/apikey)."
        )

    index_name = os.getenv("MOSS_INDEX_NAME", "moss-adk-demo-index")

    seed_client = MossClient(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
    )
    await seed_index_if_needed(seed_client, index_name)

    moss = MossSearchTool(index_name=index_name)

    agent = Agent(
        name="moss_support_agent",
        model=os.getenv("ADK_MODEL", "gemini-2.5-flash"),
        description="Customer support agent backed by Moss.",
        instruction=(
            "Answer the user's question using the `moss_search` tool. "
            "Quote results faithfully. Keep replies short."
        ),
        tools=[moss.search_tool],
    )

    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID
    )

    question = "How long do refunds take?"
    print(f"\nUser: {question}\n")
    content = types.Content(
        role="user", parts=[types.Part.from_text(text=question)]
    )

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=content
    ):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if part.text:
                print(f"{event.author}: {part.text}")
            if part.function_call:
                print(
                    f"-> tool call: {part.function_call.name}"
                    f"({part.function_call.args})"
                )


if __name__ == "__main__":
    asyncio.run(main())
