"""Multi-agent travel planner using OpenAI Agents SDK + Moss semantic search.

Three specialist agents each search their own Moss index, then a planner
agent synthesizes findings into an actionable travel plan.
"""

import asyncio
import json
import os

from agents import Agent, Runner
from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

from moss_openai_agents import moss_search_tool

load_dotenv()

client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

INDEXES = {
    "travel-destinations": {
        "file": "destinations_moss.json",
        "name": "Destinations Specialist",
        "instructions": (
            "You are a travel destination expert. "
            "Always use the moss_search tool to find information. "
            "Return all relevant results from the knowledge base."
        ),
    },
    "travel-stays": {
        "file": "stays_moss.json",
        "name": "Hotels & Stays Specialist",
        "instructions": (
            "You are an accommodation expert. "
            "Always use the moss_search tool to find hotels and stays. "
            "Return all relevant results from the knowledge base."
        ),
    },
    "travel-activities": {
        "file": "activities_moss.json",
        "name": "Activities & Tours Specialist",
        "instructions": (
            "You are an activities and tours expert. "
            "Always use the moss_search tool to find experiences. "
            "Return all relevant results from the knowledge base."
        ),
    },
}


async def setup_indexes():
    """Create travel indexes from Moss-formatted JSON data."""
    for index_name, config in INDEXES.items():
        path = os.path.join(DATA_DIR, config["file"])
        with open(path) as f:
            raw = json.load(f)

        docs = [
            DocumentInfo(id=item["id"], text=item["text"], metadata=item.get("metadata", {}))
            for item in raw
        ]

        print(f"Setting up '{index_name}' ({len(docs)} docs)...")
        try:
            await client.create_index(index_name, docs)
        except RuntimeError as e:
            if "already exists" not in str(e):
                raise
            print("  Already exists, skipping.")
        await client.load_index(index_name)
        print("  Loaded.")
    print()


def build_agents() -> tuple[list[Agent], Agent]:
    """Create 3 specialist agents and a travel planner."""
    specialists = []
    for index_name, config in INDEXES.items():
        search = moss_search_tool(client=client, index_name=index_name, top_k=5)
        specialists.append(
            Agent(
                name=config["name"],
                instructions=config["instructions"],
                tools=[search],
            )
        )

    planner = Agent(
        name="Travel Planner",
        instructions=(
            "You are an experienced travel planner. "
            "Use the specialist agents to research destinations, stays, and activities, "
            "then create a clear, actionable travel plan. "
            "Never make up information — only use what the specialists return."
        ),
        tools=[
            agent.as_tool(
                tool_name=agent.name.lower().replace(" ", "_").replace("&", "and"),
                tool_description=f"Ask the {agent.name} to search for relevant information.",
            )
            for agent in specialists
        ],
    )
    return specialists, planner


async def chat():
    """Interactive travel planner chat."""
    _, planner = build_agents()

    print("=== Moss + OpenAI Agents SDK Travel Planner ===")
    print("Plan your next trip! Type 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if not question or question.lower() in ("quit", "exit", "q"):
            if question:
                print("Goodbye!")
            break

        result = await Runner.run(planner, input=question)
        print(f"\nAgent: {result.final_output}\n")


if __name__ == "__main__":
    asyncio.run(setup_indexes())
    asyncio.run(chat())
