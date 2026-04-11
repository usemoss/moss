"""Live platform tests for Moss + OpenAI Agents SDK tools.

Run: python test_live.py

Requires MOSS_PROJECT_ID and MOSS_PROJECT_KEY in environment or .env file.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from moss import MossClient

from moss_openai_agents import (
    moss_add_docs_tool,
    moss_delete_docs_tool,
    moss_get_docs_tool,
    moss_list_indexes_tool,
    moss_search_tool,
    moss_search_with_filter_tool,
)

load_dotenv()

PROJECT_ID = os.getenv("MOSS_PROJECT_ID")
PROJECT_KEY = os.getenv("MOSS_PROJECT_KEY")
TEST_INDEX = "openai-agents-live-test"

passed = 0
failed = 0


def report(name, success, detail=""):
    global passed, failed
    if success:
        passed += 1
    else:
        failed += 1
    status = "PASS" if success else "FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


async def run_tests():
    if not PROJECT_ID or not PROJECT_KEY:
        print("ERROR: MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set.")
        sys.exit(1)

    print("Running live tests against Moss platform...\n")
    client = MossClient(PROJECT_ID, PROJECT_KEY)

    # --- 1. Add documents ---
    print("1. moss_add_docs")
    add_tool = moss_add_docs_tool(client, TEST_INDEX)
    try:
        # Create index first
        from moss import DocumentInfo
        await client.create_index(
            TEST_INDEX,
            [DocumentInfo(id="seed", text="Seed document for index creation.")],
        )
    except RuntimeError as e:
        if "already exists" not in str(e):
            raise

    try:
        result = await add_tool.on_invoke_tool(
            None,
            '{"texts": ["Moss delivers sub-10ms semantic search.", "OpenAI Agents SDK orchestrates tool-using agents.", "Python is popular for AI development."], "ids": ["doc-1", "doc-2", "doc-3"]}',
        )
        report("add 3 docs", "Added 3" in result, result)
    except Exception as e:
        report("add 3 docs", False, str(e))

    # --- 2. Search ---
    print("2. moss_search")
    search_tool = moss_search_tool(client, TEST_INDEX, top_k=3)
    try:
        result = await search_tool.on_invoke_tool(None, '{"query": "semantic search"}')
        report("search", "Result" in result, result[:80])
    except Exception as e:
        report("search", False, str(e))

    # --- 3. Search with filter ---
    print("3. moss_search_with_filter")
    filter_tool = moss_search_with_filter_tool(client, TEST_INDEX, top_k=3)
    try:
        result = await filter_tool.on_invoke_tool(None, '{"query": "search"}')
        report("search (no filter)", "Result" in result or "No relevant" in result, result[:80])
    except Exception as e:
        report("search (no filter)", False, str(e))

    # --- 4. Get documents ---
    print("4. moss_get_docs")
    get_tool = moss_get_docs_tool(client, TEST_INDEX)
    try:
        result = await get_tool.on_invoke_tool(None, '{"doc_ids": ["doc-1"]}')
        report("get by ID", "doc-1" in result, result[:80])
    except Exception as e:
        report("get by ID", False, str(e))

    # --- 5. List indexes ---
    print("5. moss_list_indexes")
    list_tool = moss_list_indexes_tool(client)
    try:
        result = await list_tool.on_invoke_tool(None, '{}')
        report("list indexes", TEST_INDEX in result or "docs" in result, result[:80])
    except Exception as e:
        report("list indexes", False, str(e))

    # --- 6. Delete documents ---
    print("6. moss_delete_docs")
    delete_tool = moss_delete_docs_tool(client, TEST_INDEX)
    try:
        result = await delete_tool.on_invoke_tool(None, '{"doc_ids": ["doc-1", "doc-2", "doc-3"]}')
        report("delete docs", "Deleted 3" in result, result)
    except Exception as e:
        report("delete docs", False, str(e))

    # --- Cleanup ---
    print("\nCleanup...")
    try:
        await client.delete_index(TEST_INDEX)
        print(f"  Deleted test index '{TEST_INDEX}'.")
    except Exception:
        print(f"  Could not delete '{TEST_INDEX}' (may not exist).")

    print(f"\nResults: {passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(run_tests())
