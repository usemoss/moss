import asyncio
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from daytona import Daytona, DaytonaConfig
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from moss import MossClient

from log_ingest import get_log_search_tool, parse_log_lines

load_dotenv()

# Read the mock log generator once at import time
_MOCK_SCRIPT = Path(__file__).parent.joinpath("mock_logs.py").read_text()

_SYSTEM_PROMPT = (
    "You are a site reliability engineer analysing logs from a production sandbox. "
    "Always call log_search with a targeted query before answering. "
    "Highlight errors and warnings, identify patterns, and give actionable insights. "
    "Be concise — one paragraph or a short bullet list."
)

def _generate_logs(sandbox) -> List[str]:
    """Run mock_logs.py in the sandbox and return the captured log lines."""
    response = sandbox.process.code_run(_MOCK_SCRIPT)
    if response.exit_code != 0:
        raise RuntimeError(f"Log generation failed: {response.result}")
    return [ln for ln in (response.result or "").splitlines() if ln.strip()]


async def _index_logs(log_lines: List[str], index_name: str) -> int:
    """Parse log lines and create a MOSS index. Returns number of entries indexed."""
    client = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
    documents = parse_log_lines(log_lines, source="app")
    if not documents:
        raise ValueError("No log entries parsed.")
    print(f"Indexing {len(documents)} log entries (index: {index_name})...")
    result = await client.create_index(index_name, documents)
    print(f"Index ready  (job_id: {result.job_id})")
    return len(documents)


async def _build_agent(index_name: str):
    """Create a LangChain agent wired to the MOSS log search tool."""
    search_tool = await get_log_search_tool(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
        index_name=index_name,
        top_k=7,
    )
    llm = ChatOpenAI(model="gpt-5.1", temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    agent = create_agent(llm, [search_tool], system_prompt=_SYSTEM_PROMPT)
    return agent



async def log_qa_agent(question: Optional[str] = None) -> None:
    """
    Run the log Q&A agent.

    Args:
        question: Single question to answer then exit.
                  Pass ``None`` for an interactive REPL.
    """
    config = DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"])
    daytona = Daytona(config)

    print("Creating Daytona sandbox...")
    sandbox = daytona.create()
    print(f"Sandbox ready  (id: {sandbox.id})\n")

    index_name = f"logs_{sandbox.id[:8]}"

    try:
        print("Generating logs in sandbox...")
        log_lines = _generate_logs(sandbox)

        n = await _index_logs(log_lines, index_name)
        print(f"\nReady — {n} log entries indexed and searchable.\n")

        executor = await _build_agent(index_name)

        async def ask(q: str) -> str:
            result = await executor.ainvoke({"messages": [("human", q)]})
            return result["messages"][-1].content

        if question:
            print(f"Q: {question}")
            print(f"\nA: {await ask(question)}\n")
        else:
            print("Log Q&A ready. Type 'quit' to exit.\n")
            print("Try: 'What errors occurred?'  /  'Any memory pressure?'  /  'DB issues?'\n")
            while True:
                try:
                    user_input = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break
                if user_input.lower() in ("quit", "exit", "q"):
                    break
                if not user_input:
                    continue
                try:
                    print(f"\nAgent: {await ask(user_input)}\n")
                except Exception as exc:
                    print(f"\nError: {exc}\n")

    finally:
        print("\nCleaning up...")
        try:
            daytona.delete(sandbox)
        except Exception as exc:
            print(f"Warning: sandbox cleanup failed: {exc}")
        try:
            moss = MossClient(os.environ["MOSS_PROJECT_ID"], os.environ["MOSS_PROJECT_KEY"])
            await moss.delete_index(index_name)
            print(f"Index '{index_name}' deleted.")
        except Exception as exc:
            print(f"Warning: index cleanup failed: {exc}")
        print("Done.")



async def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Log Q&A agent — MOSS + Daytona")
    parser.add_argument("--question", "-q", metavar="QUESTION",
                        help="Single question (omit for interactive REPL)")
    args = parser.parse_args()
    await log_qa_agent(question=args.question)


if __name__ == "__main__":
    asyncio.run(main())
