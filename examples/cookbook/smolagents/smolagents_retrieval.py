"""
Moss + Smolagents: High-Performance Retrieval Tool

This cookbook example shows how to subclass `smolagents.Tool` to create a custom 
retrieval tool for a Moss index. By calling `load_index()` beforehand, we ensure 
that the search happens locally in memory (usually <10ms latency).

Required Environment Variables:
- MOSS_PROJECT_ID: Your Moss project ID  
- MOSS_PROJECT_KEY: Your Moss project key
- MOSS_INDEX_NAME: Name of the index you want to query
"""

import asyncio
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from smolagents import CodeAgent, Tool, LiteLLMModel
from inferedge_moss import MossClient, QueryOptions

# Load environment variables
load_dotenv()

class MossRetrievalTool(Tool):
    """
    A custom tool for smolagents that performs semantic search using Moss.
    """
    name = "moss_retrieval"
    description = (
        "Finds relevant information from the company's internal documentation "
        "using semantic search. Useful for answering specific questions where "
        "the answer is likely in the knowledge base."
    )
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query string.",
        },
        "top_k": {
            "type": "integer",
            "description": "The number of results to return (default 5).",
            "nullable": True,
        },
        "metadata_filter": {
            "type": "object",
            "description": "Optional metadata filter (e.g. {'category': 'refunds'}).",
            "nullable": True,
        },
    }
    output_type = "string"

    def __init__(self, client: MossClient, index_name: str):
        super().__init__()
        self.client = client
        self.index_name = index_name

    def forward(self, query: str, top_k: int = 5, metadata_filter: Optional[Dict[str, Any]] = None) -> str:
        """
        Executes the search via the Moss client.
        Note: MossClient uses async operations, but smolagents' Tool.forward is sync.
        We bridge this using asyncio.run() since we are in a sync context here.
        """
        options = QueryOptions(
            top_k=top_k or 5,
            filter=metadata_filter
        )
        
        # Run the async query in a synchronous context
        results = asyncio.run(self.client.query(self.index_name, query, options))
        
        if not results.docs:
            return "No relevant information found."

        # Format results so the agent can easily read them
        output = []
        for doc in results.docs:
            output.append(f"--- Result ID: {doc.id} (Score: {doc.score:.3f}) ---\n{doc.text}\n")
            
        return "\n".join(output)

def main():
    # 1. Setup Moss configuration
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME")

    if not all([project_id, project_key, index_name]):
        print("Error: Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in your environment.")
        return

    # 2. Initialize and LOAD the index
    # IMPORTANT: Loading the index into memory is what enables sub-10ms queries.
    client = MossClient(project_id, project_key)
    
    print(f"Loading Moss index '{index_name}' into local memory...")
    try:
        # Since main() is sync, we use asyncio.run to load the index
        asyncio.run(client.load_index(index_name))
        print("Index loaded successfully! Sub-10ms retrieval enabled.")
    except Exception as e:
        print(f"Failed to load index: {e}")
        return

    # 3. Create the retrieval tool
    retrieval_tool = MossRetrievalTool(client, index_name)

    # 4. Initialize the Agent
    # For this example, we use the LiteLLMModel (standard in smolagents)
    model = LiteLLMModel("gpt-4o") # You can swap this with another model
    
    agent = CodeAgent(
        tools=[retrieval_tool], 
        model=model,
        add_base_tools=True 
    )

    # 5. Run the agent
    question = "What is the policy for processing refunds for digital goods?"
    print(f"\nUser Question: {question}")
    print("-" * 50)
    
    # We call agent.run() synchronously to avoid asyncio event loop conflicts
    response = agent.run(question)
    
    print("\n--- Final Agent Response ---")
    print(response)

if __name__ == "__main__":
    main()
