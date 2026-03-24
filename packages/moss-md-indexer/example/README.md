# Example Usage

This directory contains example scripts demonstrating how to use the `@moss-tools/md-indexer` library.

## Example

### `build-and-upload.ts` - Advanced Usage Examples

Demonstrates separate usage of `buildJsonDocs()` and `createIndex()` functions for more control:

- **Example 1**: Build index to JSON file, then upload separately
- **Example 2**: Build index in memory and upload directly
- **Example 3**: Build index only (no upload) for inspection
- **Example 4**: Upload an existing JSON index file

## Running the Examples

1. **Install dependencies** (from the example directory):

   ```bash
   cd example
   pnpm install
   ```

2. **Create a `.env` file** in the root of the package (or in this directory) with your Moss credentials:

   ```env
   MOSS_PROJECT_ID=your-project-id
   MOSS_PROJECT_KEY=your-project-key
   MOSS_INDEX_NAME=your-index-name
   MOSS_MODEL_NAME=moss-minilm  # Optional, defaults to 'moss-minilm'
   ```

3. **Update the paths** in the example files to point to your actual documentation directory.

4. **Run an example**:

   ```bash
   # Run the build-and-upload examples
   npx tsx build-and-upload.ts
   ```

   Or if you have a `start` script configured:

   ```bash
   pnpm start
   ```

## Note

These examples use the package from the parent directory as specified in `package.json`. The import statements are:

```typescript
// Simple usage
import { sync } from '@moss-tools/md-indexer'

// Advanced usage
import { buildJsonDocs, createIndex, uploadDocuments } from '@moss-tools/md-indexer'
import type { MossCreds } from '@moss-tools/md-indexer'
```

## Code

- **`build-and-upload.ts`**: Shows advanced usage patterns
  - Building index to file vs in-memory
  - Uploading from file vs from documents array
  - Building without uploading
  - Uploading existing files
