import { MossClient } from '@moss-dev/moss'


import 'dotenv/config'
const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!)

const indexName = 'demo-customer_faqs'

async function main() {
  // ==========================load the index============================
  await client.loadIndex(indexName)
  console.log('Index loaded successfully.')

  // ==========================query the index============================
  const results = await client.query(indexName, 'How do I return a damaged product?', {
    topK: 3,
    alpha: 0.6,
    filter: { field: 'category', condition: { $eq: 'returns' } },
  })

  const doc = results.docs[0]
  console.log(`  ID: ${doc.id}`)
  console.log(`  Text: ${doc.text}`)
  console.log(`  Score: ${doc.score}`)
  console.log(`  Metadata: ${JSON.stringify(doc.metadata)}`)
  // =============================================================================
}

main()
