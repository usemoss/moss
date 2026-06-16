# OpenAI Agents + Moss Cookbook

This cookbook demonstrates how to build an AI agent using the [OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python) and retrieve real-time context from a local knowledge base using [Moss](https://docs.moss.dev).

Instead of calling external API search services, this example registers a local function tool decorated with `@function_tool` that queries Moss with sub-10ms latency.

## Setup

1. Copy the `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your environment variables:
   - `MOSS_PROJECT_ID`
   - `MOSS_PROJECT_KEY`
   - `MOSS_INDEX_NAME`
   - `OPENAI_API_KEY`

3. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

## Running the Example

Run the script to start the agent:
```bash
python example.py
```

The script will:
1. Initialize the `MossClient` and load the specified index into memory.
2. Define a retrieval tool `moss_search` using `@function_tool`.
3. Create an OpenAI `Agent` configured with `tools=[moss_search]`.
4. Ask a question about "refund policy" and output the agent's final response after retrieving the correct context.
