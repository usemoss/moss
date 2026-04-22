import asyncio
import sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://attributable-marni-electrosurgical.ngrok-free.dev/mcp"


async def main(query: str) -> None:
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            result = await session.call_tool(
                "search_knowledge_base", {"query": query}
            )
            print("---RESULT---")
            for c in result.content:
                print(getattr(c, "text", c))


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "how do I reset my password"
    asyncio.run(main(q))
