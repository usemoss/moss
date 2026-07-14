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
// The promise stays fulfilled (true/false) so a startup failure never becomes
// an unhandled rejection — search requests branch on the result instead.
const indexReady = client.loadIndex(process.env.MOSS_INDEX_NAME!)
  .then(() => { console.log('[MOSS] index loaded locally'); return true; })
  .catch((err: unknown) => { console.error('[MOSS] loadIndex failed:', err); return false; });

const MOSS_TOOL = {
  type: 'function' as const,
  name: 'search_knowledge_base',
  description: searchTool.description,
  parameters: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'Concise search query' },
      topK: { type: 'integer', minimum: 1, maximum: 100, description: 'Number of results to return (1–100, default 5)' },
    },
    required: ['query'],
  },
};

// POST (empty body)  → mint a short-lived WebSocket token via Vercel AI Gateway
// POST ({ query })   → execute MOSS search on behalf of the realtime model's tool call
//
// Auth: fails closed (401) unless ALLOW_UNAUTHENTICATED_DEMO=true is explicitly set.
// For production, replace this check with a real session/token verification.
export async function POST(req: Request) {
  if (process.env.ALLOW_UNAUTHENTICATED_DEMO !== 'true') {
    return new Response('Unauthorized', { status: 401 });
  }

  const body = await req.json().catch(() => ({})) as Record<string, unknown>;

  if (typeof body.query === 'string') {
    if (!(await indexReady)) {
      return new Response('Search index unavailable', { status: 503 });
    }
    const topK = Number.isInteger(body.topK) ? Math.min(100, Math.max(1, body.topK as number)) : 5;
    const result = await searchTool.execute!(
      { query: body.query, topK },
      { toolCallId: 'realtime', messages: [], abortSignal: req.signal, context: {} },
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
