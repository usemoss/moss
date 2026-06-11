import asyncio
import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from moss import MossClient
from moss_adk_tool import create_moss_tool

load_dotenv()


async def main():
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME")

    if not all([project_id, project_key, index_name]):
        raise EnvironmentError(
            "Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME "
            "in your environment or .env file."
        )

    # Note: Google ADK typically requires GEMINI_API_KEY to be set in the environment.
    if not os.getenv("GEMINI_API_KEY"):
        raise EnvironmentError(
            "Please set GEMINI_API_KEY in your environment or .env file."
        )

    client = MossClient(project_id, project_key)

    # Load the index into local memory before the agent runs.
    # This one-time setup is what enables sub-10ms retrieval inside the agent loop.
    print(f"Loading index '{index_name}' into local memory...")
    await client.load_index(index_name)
    print("Index loaded.\n")

    # Create the ADK compatible tool
    retrieval_tool = create_moss_tool(client, index_name)

    # Initialize the Google ADK Agent
    agent = Agent(
        name="moss_assistant",
        model="gemini-2.5-flash",
        tools=[retrieval_tool],
    )

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=agent)

    question = "What is the policy for processing refunds for digital goods?"
    print(f"Question: {question}")
    print("-" * 50)

    # Format the input message
    content = types.Content(role="user", parts=[types.Part(text=question)])

    print("\n--- Agent Response ---")
    
    # Run the agent asynchronously via the runner
    async for event in runner.run_async(
        user_id="user_demo",
        session_id="session_demo",
        new_message=content
    ):
        if hasattr(event, "is_final_response") and event.is_final_response():
            print(event.content.parts[0].text)



if __name__ == "__main__":
    asyncio.run(main())
