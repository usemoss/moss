/**
 * Standalone script to build and upload the Moss search index.
 * Run this before `pnpm documentation:dev` to populate the index,
 * or any time you add/change markdown content.
 *
 * Usage:
 *   pnpm index:docs                          <- build + upload documentation/ (default)
 *   pnpm index:docs docs                     <- build + upload docs/ instead
 *   pnpm index:docs documentation --inspect  <- dump chunks to JSON without uploading
 */

import { buildJsonDocs, createIndex } from '@moss-tools/md-indexer'
import dotenv from 'dotenv'
import path from 'node:path'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'

dotenv.config()

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const target = process.argv[2] ?? 'documentation'
const inspect = process.argv.includes('--inspect')
const root = path.resolve(__dirname, '..', target)
const tempFile = path.resolve(__dirname, '../.index-preview.json')

// Build all chunks from the markdown files
console.log(`Building index from: ${root}`)
const allDocs = await buildJsonDocs(root) as any[]
console.log(`Built ${allDocs.length} chunks`)

// Filter out chunks with 3 or fewer words in the text field — these are
// typically empty sections, lone headings, or nav-only content not worth indexing
const filtered = allDocs.filter((doc: any) => {
  const wordCount = doc.text?.trim().split(/\s+/).filter(Boolean).length ?? 0
  return wordCount > 3
})

console.log(`After filtering (>3 words): ${filtered.length} chunks (removed ${allDocs.length - filtered.length})`)

// Write filtered chunks to temp file (used for inspect and upload)
fs.writeFileSync(tempFile, JSON.stringify(filtered, null, 2))

if (inspect) {
  console.log('\nSample (first 3 chunks):')
  console.log(JSON.stringify(filtered.slice(0, 3), null, 2))
  console.log(`\nFull output written to .index-preview.json`)
  process.exit(0)
}

const projectId = process.env.MOSS_PROJECT_ID
const projectKey = process.env.MOSS_PROJECT_KEY
const indexName = process.env.MOSS_INDEX_NAME

if (!projectId || !projectKey || !indexName) {
  console.error('Missing env vars: MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME')
  process.exit(1)
}

console.log(`Uploading to index: ${indexName}`)
await createIndex(tempFile, { projectId, projectKey, indexName, modelName: 'moss-minilm' })

// Clean up temp file
fs.unlinkSync(tempFile)

console.log('Done.')
