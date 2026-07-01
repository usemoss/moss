from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from moss import DocumentInfo, MossClient

from moss_multitenant import IndexStore, build_tools

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"


BUSINESSES: dict[str, dict[str, str]] = {
    "food-luigis-pizzeria": {
        "name": "Luigi's Pizzeria",
        "data_file": "pizza_shop.json",
        "tool_description": (
            "Search Luigi's Pizzeria knowledge base. "
            "Covers menu items, pizza prices, toppings, delivery zones, opening hours, "
            "weekly specials, and how to place an order. Use for food, restaurant, or pizza questions."
        ),
    },
    "law-harrison-cole": {
        "name": "Harrison & Cole LLP",
        "data_file": "law_firm.json",
        "tool_description": (
            "Search Harrison & Cole LLP knowledge base. "
            "Covers legal practice areas, attorney profiles, hourly rates, flat-fee services, "
            "retainer packages, consultation booking, and the client engagement process. "
            "Use for legal, law firm, attorney, or contract questions."
        ),
    },
    "tech-stackbase": {
        "name": "Stackbase",
        "data_file": "saas_company.json",
        "tool_description": (
            "Search Stackbase knowledge base. "
            "Covers SaaS pricing plans (Free / Pro / Enterprise), API rate limits, SDKs, "
            "onboarding steps, integrations, security certifications, and billing. "
            "Use for software, SaaS, developer tools, or API questions."
        ),
    },
    "health-vitacare": {
        "name": "VitaCare Clinic",
        "data_file": "health_vitacare.json",
        "tool_description": (
            "Search VitaCare Clinic knowledge base. "
            "Covers medical services, physician profiles, clinic hours, appointment booking, "
            "accepted insurance plans, self-pay fees, telehealth, and prescription refills. "
            "Use for healthcare, medical, clinic, or doctor questions."
        ),
    },
    "retail-urban-threads": {
        "name": "Urban Threads",
        "data_file": "retail_urban_threads.json",
        "tool_description": (
            "Search Urban Threads knowledge base. "
            "Covers clothing catalog, brand prices, store hours, return policy, shipping, "
            "sizing guide, loyalty programme, and sustainability info. "
            "Use for clothing, retail, fashion, or shopping questions."
        ),
    },
}

SYSTEM_PROMPT = (
    "You are a helpful local business directory assistant. "
    "You have access to knowledge bases for five different businesses. "
    "Always use the search tools to find accurate information before answering. "
    "If a question could relate to more than one business, search all relevant indexes "
    "and synthesise the results. Always cite which business the information came from."
)


class MultiTenantAgent:
    """
    Agent with one search tool per Moss index.

    Uses llm.bind_tools() + a manual async loop — no AgentExecutor, no
    LangGraph graph. Ambiguous questions trigger parallel Moss queries via
    asyncio.gather before the model synthesises the final answer.
    """

    def __init__(self, store: IndexStore, model: str = "gpt-4.1-mini") -> None:
        tools = build_tools(BUSINESSES, store)
        llm = ChatOpenAI(
            model=model,
            temperature=0,
            api_key=os.environ["OPENAI_API_KEY"],
        )
        self._llm = llm.bind_tools(tools)
        self._tool_map = {t.name: t for t in tools}

    async def chat(self, user_message: str) -> str:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        while True:
            response = await self._llm.ainvoke(messages)
            messages.append(response)

            if not response.tool_calls:
                return response.content

            # Run all tool calls the model issued in this turn concurrently
            results = await asyncio.gather(*[
                self._tool_map[tc["name"]].ainvoke(tc["args"])
                for tc in response.tool_calls
            ])

            for tc, result in zip(response.tool_calls, results):
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

async def setup_indexes(client: MossClient) -> None:
    """Create each business index separately from its data file."""
    for index_name, config in BUSINESSES.items():
        path = DATA_DIR / config["data_file"]
        raw = json.loads(path.read_text())
        docs = [
            DocumentInfo(id=item["id"], text=item["text"], metadata=item.get("metadata", {}))
            for item in raw
        ]
        print(f"  {index_name}: {len(docs)} docs", end=" ... ")
        try:
            await client.create_index(index_name, docs)
            print("created")
        except RuntimeError as e:
            if "already exists" in str(e).lower():
                print("already exists, skipping")
            else:
                raise


DEMO_QUESTIONS = [
    "Do you offer gluten-free pizza?",
    "What are the hourly legal fees?",
    "How do I get started with the free plan?",
    "Can I book a telehealth appointment on a Saturday?",
    "What is your return policy for online orders?",
]


async def run_demo(agent: MultiTenantAgent) -> None:
    print("MULTI-TENANT INDEX ROUTING DEMO — LangChain + OpenAI")
    print("Model selects which Moss index(es) to search via tool calling")

    for question in DEMO_QUESTIONS:
        print(f"\nQ: {question!r}")
        answer = await agent.chat(question)
        print(f"\nFinal answer:\n{answer}")


async def main(question: str | None = None) -> None:
    client = MossClient(
        os.environ["MOSS_PROJECT_ID"],
        os.environ["MOSS_PROJECT_KEY"],
    )

    print("Setting up indexes...")
    await setup_indexes(client)

    store = IndexStore(client, top_k=5)
    agent = MultiTenantAgent(store)

    if question:
        print(f"\nQ: {question!r}\n")
        answer = await agent.chat(question)
        print(answer)
    else:
        await run_demo(agent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-tenant index routing demo")
    parser.add_argument("--q", dest="question", help="Single question to ask")
    args = parser.parse_args()
    asyncio.run(main(args.question))
