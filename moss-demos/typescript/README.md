# Moss TypeScript Examples

These examples show how to search through an index using the Moss TypeScript SDK.

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create a `.env` file in the root of the project (copy from `.env.example`) and fill in your credentials:

   ```env
   MOSS_PROJECT_ID=your-project-id
   MOSS_PROJECT_KEY=your-project-key
   ```

## Files

### simple_quickstart.ts

Loads an index and runs a basic search query. Good starting point.

```bash
npx tsx simple_quickstart.ts
```

### advance_query.ts

Same as the simple example but with extra options:

- `topK` — how many results to return
- `alpha` — controls the balance between keyword and semantic search (0 = keyword only, 1 = semantic only)
- `filter` — narrows results by metadata (e.g. only show documents in the `returns` category)

```bash
npx tsx advance_query.ts
```

## What the output looks like

```text
Index loaded successfully.
  ID: doc-42
  Text: You can return damaged products within 30 days...
  Score: 0.91
  Metadata: {"category":"returns"}
```

## Resources

- [Docs](https://docs.moss.dev/?utm_source=github&utm_medium=readme&utm_campaign=typescript-examples)
- [Portal](https://portal.usemoss.dev/?utm_source=github&utm_medium=readme&utm_campaign=typescript-examples)
- [GitHub](https://github.com/usemoss/moss)
- [Discord](https://discord.com/invite/eMXExuafBR?utm_source=github&utm_medium=readme&utm_campaign=typescript-examples)
