# Mastra + Moss Cookbook

This cookbook example demonstrates how to integrate [Moss](https://moss.dev/) fast semantic search as a native tool within a [Mastra](https://mastra.ai/) Agent.

By wrapping `MossClient` inside a Mastra `createTool()` primitive, we can empower our Mastra conversational agents to query large semantic indexes natively with sub-10 ms retrieval latency!

## Prerequisites

1. Moss Account (Create one at [moss.dev](https://moss.dev/))
2. OpenAI Account (for the LLM powering the agent)
3. Node.js

## Setup

Navigate to this directory and install dependencies:

```bash
npm install
```

Configure your environment variables. You can copy the variables to a local `.env` file either here or in the root of the moss repository. 

```bash
MOSS_PROJECT_ID=your_moss_project_id
MOSS_PROJECT_KEY=your_moss_project_key
MOSS_INDEX_NAME=support-docs
OPENAI_API_KEY=sk-...
```

_Note_: Ensure you have populated the index specified by `MOSS_INDEX_NAME` with documents (e.g. by running the standard python or javascript ingestion examples).

## Run the Example

### 1. Create the Index

Before running the agent, initialize your Moss index with sample FAQ data:

```bash
npm run create-index
```

### 2. Start the Agent

Execute the TypeScript file using `tsx`:

```bash
npm start
```

### What happens?

1. Mastra creates a `Knowledge Support Copilot` agent connected to GPT-4.1-mini.
2. The agent is provided with `mossSearchTool` representing Moss querying.
3. The prompt is presented to the agent.
4. The agent decides it needs to query the Moss tool to answer the question accurately.
5. The `moss-search` tool executes and retrieves relevant paragraphs using the fast `MossClient`.
6. Mastra streams the tool output back into the prompt buffer context, and returns a fully cited response!

## Running Tests

Unit tests mock `MossClient` and validate the tool execute functions without requiring live API credentials:

```bash
npm test
```

The test suite covers:

- `executeMossSearch`: doc shape mapping (`text` → `content`), empty results, correct arguments forwarded to `client.query`
- `executeMossIndex`: provided doc ID passthrough, auto-generated `doc_*` ID, correct arguments forwarded to `client.addDocs`

## Project Structure

```text
.
├── moss_mastra.ts      # Mastra tool definitions and agent setup
├── create_index.ts     # One-time script to seed the Moss index with sample data
├── seed_data.ts        # Sample FAQ documents
└── test_mastra.ts      # Unit tests (no API credentials required)
```
