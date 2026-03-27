import os
import json
import asyncio
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from inferedge_moss import MossClient, DocumentInfo
from moss_crewai import MossSearchTool, moss_tools

load_dotenv()

gemini_llm = LLM(
    model="gemini/gemini-3.1-flash-lite-preview",
    api_key=os.getenv("GEMINI_API_KEY"),
)

INDEX_NAME = "crewai-faq-demo"


async def setup_index():
    """Create a Moss index with the first 10 FAQ documents."""
    client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))

    faqs_path = os.path.join(os.path.dirname(__file__), "..", "..", "python", "faqs.json")
    with open(faqs_path, "r") as f:
        faqs = json.load(f)

    docs = [
        DocumentInfo(
            id=faq["id"],
            text=faq["text"],
            metadata={k: str(v) for k, v in faq.get("metadata", {}).items()},
        )
        for faq in faqs[:10]
    ]

    print(f"Setting up index '{INDEX_NAME}' with {len(docs)} documents...")
    try:
        await client.create_index(INDEX_NAME, docs)
        print("Index created.")
    except RuntimeError as e:
        if "already exists" in str(e):
            print("Index already exists, skipping creation.")
        else:
            raise
    print("Loading index for local queries...")
    await client.load_index(INDEX_NAME)
    print("Index loaded and ready.\n")


def single_agent_example():
    """A single researcher agent that uses Moss to answer questions."""

    search = MossSearchTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=INDEX_NAME,
        top_k=3,
    )

    researcher = Agent(
        role="Customer Support Agent",
        goal="Answer customer questions accurately using the FAQ knowledge base",
        backstory="You are a helpful customer support agent with access to the company FAQ database.",
        tools=[search],
        llm=gemini_llm,
        verbose=True,
    )

    task = Task(
        description="A customer asks: 'What is your return policy and do you ship internationally?'",
        expected_output="A helpful, concise answer addressing both questions based on the knowledge base.",
        agent=researcher,
    )

    crew = Crew(agents=[researcher], tasks=[task], verbose=True)
    result = crew.kickoff()
    print("\n--- Single Agent Result ---")
    print(result)


def multi_agent_example():
    """A researcher finds information, a writer synthesizes it."""

    tools = moss_tools(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=INDEX_NAME,
        top_k=3,
    )
    search_tool = tools[0]

    researcher = Agent(
        role="Senior Researcher",
        goal="Find comprehensive information about the topic",
        backstory="You are an expert researcher who uses semantic search to find relevant information.",
        tools=[search_tool],
        llm=gemini_llm,
        verbose=True,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Write clear, well-structured summaries",
        backstory="You are a technical writer who synthesizes research into readable content.",
        llm=gemini_llm,
        verbose=True,
    )

    research_task = Task(
        description="Research what payment methods are accepted and how customers can manage their accounts (password reset, etc.).",
        expected_output="A detailed list of findings from the FAQ database.",
        agent=researcher,
    )

    writing_task = Task(
        description="Based on the research findings, write a concise customer-friendly FAQ summary covering payments and account management.",
        expected_output="A 2-3 paragraph summary suitable for a help page.",
        agent=writer,
    )

    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        verbose=True,
    )
    result = crew.kickoff()
    print("\n--- Multi-Agent Result ---")
    print(result)


if __name__ == "__main__":
    print("=== CrewAI + Moss Integration Examples ===\n")

    asyncio.run(setup_index())

    single_agent_example()

    #multi_agent_example()
