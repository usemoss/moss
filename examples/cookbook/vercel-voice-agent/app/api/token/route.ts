import { createGateway } from '@ai-sdk/gateway';
import { MossClient } from '@moss-dev/moss';
import { mossSearchTool } from '@moss-tools/vercel-sdk';

export const runtime = 'nodejs';

const gateway = createGateway({ apiKey: process.env.AI_GATEWAY_API_KEY });

const client = new MossClient(
  process.env.MOSS_PROJECT_ID!,
  process.env.MOSS_PROJECT_KEY!,
);

const searchTool = mossSearchTool({
  client,
  indexName: process.env.MOSS_INDEX_NAME!,
});

// Load the index into local memory at startup.
// Cloud query returns 503 — local queries work fine after loadIndex.
// Storing the promise means search requests block until ready, or fail fast if it rejects.
const indexReady = client.loadIndex(process.env.MOSS_INDEX_NAME!)
  .then(() => console.log('[MOSS] index loaded locally'))
  .catch((err: unknown) => { console.error('[MOSS] loadIndex failed:', err); throw err; });

const MOSS_TOOL = {
  type: 'function' as const,
  name: 'search_knowledge_base',
  description: searchTool.description,
  parameters: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'Concise search query' },
      topK: { type: 'number', description: 'Number of results (default 5)' },
    },
    required: ['query'],
  },
};

// ⚠️  DEMO ONLY — this route is intentionally unauthenticated.
// Before deploying publicly, add a real auth check (e.g. verify a
// NextAuth session cookie) so arbitrary callers cannot mint Gateway
// tokens or query your MOSS index.
//
// POST (empty body)  → mint a short-lived WebSocket token via Vercel AI Gateway
// POST ({ query })   → execute MOSS search on behalf of the realtime model's tool call
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({})) as Record<string, unknown>;

  if (typeof body.query === 'string') {
    try {
      await indexReady;
    } catch {
      return new Response('Search index unavailable', { status: 503 });
    }
    const topK = typeof body.topK === 'number' ? body.topK : 5;
    const result = await searchTool.execute!(
      { query: body.query, topK },
      { toolCallId: 'realtime', messages: [], abortSignal: req.signal },
    );
    const docs = (result as { docs: Array<{ text: string }> }).docs ?? [];
    return new Response(docs.map((d) => d.text).join('\n\n---\n\n'), {
      headers: { 'Content-Type': 'text/plain' },
    });
  }

  const { token, url } = await gateway.experimental_realtime.getToken({
    model: 'openai/gpt-realtime-2',
  });
  return Response.json({ token, url, tools: [MOSS_TOOL] });
}
