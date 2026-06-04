import { MossClient, DocumentInfo } from '@moss-dev/moss'
const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!)
const documents: DocumentInfo[] = [
  { id: 'doc1', text: 'How do I track my order? You can track your order by logging into your account.', metadata: { category: 'shipping' } },
  { id: 'doc2', text: 'What is your return policy? We offer a 30-day return policy for most items.', metadata: { category: 'returns' } },
  { id: 'doc3', text: 'How can I change my shipping address? Contact our customer service team.', metadata: { category: 'support' } },
]
const indexName = 'faqs'
await client.createIndex(indexName, documents, { modelId: 'moss-minilm' }) // default; use 'moss-mediumlm' for higher accuracy
await client.loadIndex(indexName)
const results = await client.query(indexName, 'How do I return a damaged product?', { topK: 3 })
console.log(results.docs[0])