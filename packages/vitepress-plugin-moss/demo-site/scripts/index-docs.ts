/**
 * Standalone script to build and upload the Moss search index.
 * Run this before `pnpm documentation:dev` to populate the index,
 * or any time you add/change markdown content.
 *
 * Usage:
 *   pnpm index:docs                          <- build + upload documentation/ (default)
 *   pnpm index:docs docs                     <- build + upload docs/ instead
 *   pnpm index:docs documentation --inspect  <- dump first 3 chunks without uploading
 */

import { sync, buildJsonDocs } from '@moss-tools/md-indexer'
import dotenv from 'dotenv'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

dotenv.config({ path: path.resolve(__dirname, '../../.env') })

const target = process.argv[2] ?? 'documentation'
const inspect = process.argv.includes('--inspect')
const root = path.resolve(__dirname, '..', target)

if (inspect) {
  const docs = await buildJsonDocs(root) as any[]
  console.log(`Built ${docs.length} chunks\n`)
  console.log('Sample (first 3 chunks):')
  console.log(JSON.stringify(docs.slice(0, 3), null, 2))
  process.exit(0)
}

await sync({ root })
