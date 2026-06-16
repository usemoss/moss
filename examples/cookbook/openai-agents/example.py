import asyncio
import os
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from moss import DocumentInfo, MossClient, QueryOptions

# Load environment variables
load_dotenv()

async def _ensure_demo_index(client: MossClient, index_name: str) -> None:
    """Create a small demo index if it does not already exist."""
    existing_indexes = await client.list_indexes()
    if any(index.name == index_name for index in existing_indexes):
        print(f"Index '{index_name}' already exists. Skipping creation.")
        return

    docs = [
        DocumentInfo(
            id="reset-password",
            text=(
                "To reset your password, go to Settings > Security, choose Reset "
                "Password, and follow the email verification link."
            ),
        ),
        DocumentInfo(
            id="refund-policy",
            text="Refunds are processed within 3-5 business days after approval.",
        ),
        DocumentInfo(
            id="support-hours",
            text="Customer support is available Monday to Friday, 9 AM to 6 PM IST.",
        ),
    ]
    await client.create_index(index_name, docs)


async def main() -> None:
    # 1. Initialize Moss Client and Load Index
    client = MossClient(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
    )
    index_name = os.getenv("MOSS_INDEX_NAME")  # e.g. "my-index"

    # Ensure the demo index exists in the cloud before pre-loading it
    await _ensure_demo_index(client, index_name)

    print(f"Pre-loading index '{index_name}' into Moss local runtime...")
    await client.load_index(index_name)

    # 2. Define the search tool using @function_tool
    @function_tool
    async def moss_search(query: str) -> list[str]:
        """Search the knowledge base for answers to the user's question.

        Args:
            query: The search query.
        """
        print(f"[Tool Triggered] Searching Moss for: '{query}'")
        result = await client.query(
            index_name,
            query,
            options=QueryOptions(top_k=3),
        )
        return [doc.text for doc in result.docs]

    # 3. Create the OpenAI Agent with the search tool
    agent = Agent(
        name="Support Assistant",
        instructions=(
            "You are a helpful customer support assistant. "
            "Use the moss_search tool to look up information and answer "
            "the user's questions about policies, hours, or password resets."
        ),
        tools=[moss_search],
    )

    # 4. Run the Agent
    print("\nRunning agent query...")
    result = await Runner.run(agent, "How long do refunds take to process?")
    print(f"\nFinal Agent Response:\n{result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
