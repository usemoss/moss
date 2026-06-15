import asyncio
import os

from dotenv import load_dotenv
from smolagents import CodeAgent, InferenceClientModel

from moss import MossClient
from tool import MossRetrievalTool

load_dotenv()


def main():
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    index_name = os.getenv("MOSS_INDEX_NAME")

    if not all([project_id, project_key, index_name]):
        raise EnvironmentError(
            "Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME "
            "in your environment or .env file."
        )

    client = MossClient(project_id, project_key)

    # Load the index into local memory before the agent runs.
    # This one-time setup is what enables sub-10ms retrieval inside the agent loop.
    print(f"Loading index '{index_name}' into local memory...")
    asyncio.run(client.load_index(index_name))
    print("Index loaded.\n")

    retrieval_tool = MossRetrievalTool(client, index_name)

    # InferenceClientModel uses the HuggingFace Inference API.
    # Set HUGGING_FACE_HUB_TOKEN in your .env if the model requires authentication.
    model = InferenceClientModel("meta-llama/Llama-3.3-70B-Instruct")
    agent = CodeAgent(tools=[retrieval_tool], model=model, add_base_tools=True)

    question = "What is the policy for processing refunds for digital goods?"
    print(f"Question: {question}")
    print("-" * 50)

    response = agent.run(question)

    print("\n--- Agent Response ---")
    print(response)


if __name__ == "__main__":
    main()
