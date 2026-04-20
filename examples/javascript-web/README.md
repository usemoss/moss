# Moss Browser SDK Examples

Examples for [`@moss-dev/moss-web`](https://www.npmjs.com/package/@moss-dev/moss-web) - in-browser semantic search powered by WASM.

## Setup

1. **Install dependencies:**

   ```bash
   npm install
   ```

2. **Start the dev server:**

   ```bash
   npm run dev
   ```

3. Open the URL printed by Vite and enter your Moss project credentials in the UI.

## Examples

### Load & Query

Load an existing index and run semantic searches entirely in-browser.

### Comprehensive

End-to-end walkthrough of every SDK operation: create index, get info, list indexes, add docs, get docs, load, query, delete docs, delete index.

### Metadata Filtering

Query with `$eq`, `$and`, `$or`, `$in`, and `$near` filters on metadata fields.

## Requirements

- A modern browser (Chrome, Firefox, Safari, Edge)
- Valid Moss project credentials (project ID + key)
