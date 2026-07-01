"""Moss + Google Agent Development Kit (ADK) cookbook.

ADK wraps a plain async function as a tool automatically when it's added to
an Agent's `tools` list — the function's name, type hints, and docstring
become the schema the model sees. `create_moss_search_tool()` returns
exactly that kind of function, bound to a Moss client and index.

This demo builds an "Onboarding Assistant" that answers new-hire questions
by searching a small company-handbook index, using OpenAI's GPT models via
ADK's LiteLLM integration.
"""
import asyncio
import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from moss import DocumentInfo, MossClient, QueryOptions

# NOTE: load_dotenv() is called in main() to avoid side effects on import.

MODEL = LiteLlm(model="openai/gpt-4.1-mini")
APP_NAME = "moss-adk-onboarding-assistant"
USER_ID = "employee"
INDEX_NAME = "onboarding-handbook"


async def ensure_demo_index(client: MossClient, index_name: str) -> None:
    """Create a small onboarding-handbook index if it doesn't already exist."""
    existing = await client.list_indexes()
    if any(index.name == index_name for index in existing):
        return
    docs = [
        DocumentInfo(
            id="pto-policy",
            text=(
                "Employees accrue 1.5 days of PTO per month, capped at 20 days per year. "
                "Request time off in Workday at least 5 business days in advance."
            ),
        ),
        DocumentInfo(
            id="expense-reports",
            text=(
                "Submit expense reports in Expensify within 30 days of purchase. "
                "Receipts are required for anything over $25."
            ),
        ),
        DocumentInfo(
            id="laptop-setup",
            text=(
                "New hires receive a MacBook Pro on day one. IT pre-installs required "
                "software; message #it-help on Slack for anything missing."
            ),
        ),
        DocumentInfo(
            id="benefits-enrollment",
            text=(
                "Health, dental, and vision benefits enrollment is open for the first "
                "30 days of employment via the HR portal."
            ),
        ),
        DocumentInfo(
            id="remote-work",
            text=(
                "Employees may work remotely up to 3 days per week. Core collaboration "
                "hours are 10am-3pm local time."
            ),
        ),
    ]
    await client.create_index(index_name, docs)


def create_moss_search_tool(client: MossClient, index_name: str, top_k: int = 3):
    """Build an ADK function tool that runs semantic search against a Moss index."""

    index_loaded = False

    async def moss_search(query: str) -> dict:
        """Search the company handbook for policies and procedures.

        Args:
            query: Natural-language question about a company policy.

        Returns:
            dict with "status" and either "results" (list of {id, text, score})
            or "message" when nothing relevant is found.
        """
        nonlocal index_loaded
        if not index_loaded:
            await client.load_index(index_name)
            index_loaded = True

        result = await client.query(index_name, query, QueryOptions(top_k=top_k))
        if not result.docs:
            return {"status": "success", "results": [], "message": "No relevant information found."}

        return {
            "status": "success",
            "results": [{"id": doc.id, "text": doc.text, "score": doc.score} for doc in result.docs],
        }

    return moss_search


async def ask(runner: Runner, session_id: str, question: str) -> str:
    """Send a question to the agent and return its final response text."""
    content = types.Content(role="user", parts=[types.Part(text=question)])
    final_response_text = "Agent did not produce a final response."

    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=content):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            break

    return final_response_text


async def main() -> None:
    load_dotenv()
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        raise RuntimeError("Missing MOSS_PROJECT_ID or MOSS_PROJECT_KEY environment variables.")
    client = MossClient(project_id, project_key)

    search = create_moss_search_tool(client, INDEX_NAME)

    agent = Agent(
        model=MODEL,
        name="onboarding_assistant",
        description="Answers new-hire questions using the company handbook.",
        instruction=(
            "You are a helpful onboarding assistant. Use the moss_search tool to look up "
            "company policy before answering, and say so when the handbook has no "
            "relevant answer."
        ),
        tools=[search],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    question = "How many vacation days do I get and how far ahead do I need to request them?"
    print(f"You: {question}\n")
    answer = await ask(runner, session.id, question)
    print(f"Agent: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
