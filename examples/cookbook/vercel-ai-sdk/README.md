# Vercel AI SDK + Moss Cookbook

This cookbook demonstrates how to integrate [Moss](https://moss.dev/) fast semantic search with the [Vercel AI SDK](https://sdk.vercel.ai/) using the `@moss-tools/vercel-sdk` package.

By passing Moss tools into `generateText` and `streamText`, AI agents can automatically retrieve sub-10ms semantic search results from a Moss index before generating a response.

## Prerequisites

1. Moss Account (Create one at [moss.dev](https://moss.dev/))
2. OpenAI Account (for the LLM powering the agent)
3. Node.js

## Setup

Navigate to this directory and install dependencies:

```bash
npm install
```

Configure your environment variables. Copy `.env.example` to `.env` either here or in the root of the moss repository:

```bash
MOSS_PROJECT_ID=your_moss_project_id
MOSS_PROJECT_KEY=your_moss_project_key
MOSS_INDEX_NAME=support-docs
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Run the Example

### 1. Create the Index

Seed your Moss index with sample FAQ data:

```bash
npm run create-index
```

### 2. Run the Agent

```bash
npm start
```

### What happens?

1. `MossVercelToolkit` loads the index into memory for fast local queries (~1-10ms).
2. `mossSearchTool` and `mossLoadIndexTool` are passed to the Vercel AI SDK.
3. **Scenario 1** — `generateText`: the LLM calls `mossSearchTool` automatically to retrieve context, then returns a grounded response.
4. **Scenario 2** — `streamText`: the same flow, streamed token-by-token to stdout.

## Project Structure

```text
.
├── moss_vercel.ts      # MossVercelToolkit — pure integration, no model references
├── example_usage.ts    # Runnable demo: generateText + streamText with Moss tools
├── create_index.ts     # One-time script to seed the Moss index with sample data
├── seed_data.ts        # Sample FAQ documents
└── .env.example        # Environment variable template
```
