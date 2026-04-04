"""Minimal demo using the convenience factory function."""

import os

from strands import Agent

from strands_agents_moss import create_moss_search_tool

# create_moss_search_tool returns a ready-to-use Strands tool.
# The index is loaded lazily on the first query.
search_tool = create_moss_search_tool(
    project_id=os.getenv("MOSS_PROJECT_ID"),
    project_key=os.getenv("MOSS_PROJECT_KEY"),
    index_name=os.getenv("MOSS_INDEX_NAME", "my-index"),
)

agent = Agent(tools=[search_tool])
agent("What are your shipping options?")
