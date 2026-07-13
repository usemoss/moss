# Moss + Vercel AI SDK Cookbook

A minimal example showing how to plug Moss semantic search into an agent
built with the Vercel AI SDK, using the official `@moss-tools/vercel-sdk`
tool wrappers.

## What this shows

- Creating a `MossClient` and wrapping one of your indexes with `mossSearchTool`
- - Handing that tool to `generateText` (single-shot answer) or `streamText`
  - (token-by-token streaming) so the model can retrieve context before replying
  - - A small CLI script you can run with your own question as an argument
   
    - ## Prerequisites
   
    - - Node.js 18+
      - - A Moss project (project id + project key) with at least one index created
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
            | `STREAM` | Optional, set to `true` to use `streamText` instead of `generateText` |

            ## Run

            ```bash
            npm start -- "What is the refund policy?"
            ```

            By default this calls `generateText` once and prints the answer. Set
            `STREAM=true` in your `.env` to switch to `streamText` and see the response
            print incrementally as it's generated.

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
