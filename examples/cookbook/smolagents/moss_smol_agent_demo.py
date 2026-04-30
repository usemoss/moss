import asyncio
import os
from dotenv import load_dotenv
from smolagents import CodeAgent, HfApiModel
from inferedge_moss import MossClient
from tool import MossRetrievalTool

# Load environment variables from .env file
load_dotenv()

def main():
    """
    Main entry point for the Moss + Smolagents demo.
    """
    # Load configuration from environment variables
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME")

    if not all([project_id, project_key, index_name]):
        print("Error: Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in your environment.")
        return

    # 1. Initialize Moss client
    client = MossClient(project_id, project_key)
    
    # 2. Load the index into local memory
    # Pre-loading the index into memory is what enables sub-10ms retrieval.
    print(f"Loading Moss index '{index_name}' into local memory...")
    try:
        # We use asyncio.run to execute the async load_index method in a sync context
        asyncio.run(client.load_index(index_name))
        print("Index loaded successfully!")
    except Exception as e:
        print(f"Failed to load index: {e}")
        return

    # 3. Create the custom retrieval tool
    retrieval_tool = MossRetrievalTool(client, index_name)

    # 4. Initialize the AI Agent
    # HfApiModel is the standard way to initialize models in smolagents.
    # Ensure HUGGING_FACE_HUB_TOKEN is set in your .env if required.
    model = HfApiModel("meta-llama/Llama-3.3-70B-Instruct") 
    
    agent = CodeAgent(
        tools=[retrieval_tool], 
        model=model,
        add_base_tools=True 
    )

    # 5. Run the agentic loop
    question = "What is the policy for processing refunds for digital goods?"
    print(f"\nUser Question: {question}")
    print("-" * 50)
    
    # agent.run() executes the tool-calling loop synchronously
    response = agent.run(question)
    
    print("\n--- Final Agent Response ---")
    print(response)

if __name__ == "__main__":
    main()
