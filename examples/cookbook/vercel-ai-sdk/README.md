# Moss + Vercel AI SDK Cookbook

A minimal example showing how to plug Moss semantic search into an agent
built with the Vercel AI SDK, using the official `@moss-tools/vercel-sdk`
tool wrappers.

## What this shows

- Creating a `MossClient` and wrapping one of your indexes with `mossSearchTool`
- - Handing that tool to `streamText` (token-by-token streaming, the default)
  - or `generateText` (single-shot answer) so the model can retrieve context
  - before replying
  - - A script to seed a small sample index so the example runs end-to-end with
    - no existing Moss data required
    - - A small CLI script you can run with your own question as an argument
     
      - ## Prerequisites
     
      - - Node.js 18+
        - - A Moss project (project id + project key). You do not need an existing
          - index, the seed script below creates one for you.
          - - An OpenAI API key
           
            - ## Install
           
            - ```bash
              cd examples/cookbook/vercel-ai-sdk
              npm install
              ```

              ## Configure

              Copy the example env file and fill in your own values:

              ```bash
              cp .env.example .env
              ```

              | Variable | Description |
              | --- | --- |
              | `MOSS_PROJECT_ID` | Your Moss project id |
              | `MOSS_PROJECT_KEY` | Your Moss project key |
              | `MOSS_INDEX_NAME` | The index the search tool should query |
              | `OPENAI_API_KEY` | Your OpenAI API key |
              | `OPENAI_MODEL` | Optional, defaults to `gpt-4o-mini` |
              | `GENERATE` | Optional, set to `true` to use `generateText` instead of the default `streamText` |

              ## Seed a sample index

              If you don't already have a Moss index to query, create one from the sample
              support-doc snippets in `seed_data.ts`:

              ```bash
              npm run seed
              ```

              This creates (or replaces) the index named by `MOSS_INDEX_NAME` in your `.env`.

              ## Run

              ```bash
              npm start -- "What is the refund policy?"
              ```

              By default this uses `streamText` and prints the answer incrementally as it's
              generated. Set `GENERATE=true` in your `.env` to switch to a single-shot
              `generateText` call instead.

              ## How it works

              `moss_vercel.ts` prebinds the search tool to a single index name with
              `mossSearchTool({ client, indexName })`, so the model only ever has to supply
              a `query` (and optional `topK`) rather than choosing an index itself. The
              system prompt instructs the model to always search before answering and to
              cite what it finds, which keeps responses grounded in your own data instead
              of the model's general knowledge.

              ## Learn more

              - [`@moss-tools/vercel-sdk` package](../../../packages/vercel-sdk)
              - - [Vercel AI SDK docs](https://sdk.vercel.ai/docs)
                - 
