import { buildJsonDocs, createIndex, uploadDocuments, sync } from '@moss-tools/md-indexer'
import type { MossCreds } from '@moss-tools/md-indexer'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import dotenv from 'dotenv'

dotenv.config()

const docsPath = fileURLToPath(new URL('./docs', import.meta.url))
const outputFile = path.join(process.cwd(), 'search-index.json')

const creds = {
  projectId: process.env.MOSS_PROJECT_ID!,
  projectKey: process.env.MOSS_PROJECT_KEY!,
  indexName: process.env.MOSS_INDEX_NAME!,
  modelName: process.env.MOSS_MODEL_NAME || 'moss-minilm'
}

async function main() {
  // Example 1: Build to file, then upload
  // const documents = await buildJsonDocs(docsPath, { outputFile })
  // await createIndex(outputFile, creds)

  // Example 2: Build in memory, upload directly
  // const documents = await buildJsonDocs(docsPath)
  // await uploadDocuments(documents, creds)

  // Example 3: Build only (no upload)
  // await buildJsonDocs(docsPath, { outputFile })

  // Example 4: Upload existing file
  // await createIndex(outputFile, creds)

  // Example 5: Sync (build and upload)
  await sync({ root: docsPath })
}

main().catch(console.error)
