import { deepgram } from '@ai-sdk/deepgram';
import { createGateway } from '@ai-sdk/gateway';
import { MossClient } from '@moss-dev/moss';
import { transcribe, generateSpeech, generateText, tool } from 'ai';
import { z } from 'zod';

export const runtime = 'nodejs';
export const maxDuration = 30;

const gateway = createGateway({ apiKey: process.env.AI_GATEWAY_API_KEY });
const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!);

// Same pattern as @moss-tools/vercel-sdk mossSearchTool — inlined to avoid ai@6/7 peer dep conflict
// TODO: replace with mossSearchTool({ client, indexName }) once @moss-tools/vercel-sdk supports ai@7
const searchTool = tool({
  description: 'Search the knowledge base for information relevant to the user\'s question.',
  inputSchema: z.object({
    query: z.string().describe('Concise search query'),
    topK: z.number().int().min(1).max(10).default(5),
  }),
  execute: async ({ query, topK }) => {
    return client.query(process.env.MOSS_INDEX_NAME!, query, { topK });
  },
});

// POST: audio → Deepgram STT → GPT-4.1 Mini + MOSS tool → Deepgram TTS → audio
export async function POST(req: Request) {
  const audioBuffer = Buffer.from(await req.arrayBuffer());
  if (!audioBuffer.length) return Response.json({ error: 'No audio' }, { status: 400 });

  // 1. Transcribe with Deepgram
  const { text: transcript } = await transcribe({
    model: deepgram.transcription('nova-3'),
    audio: audioBuffer,
  });
  if (!transcript.trim()) return new Response(null, { status: 204 });
  console.log('[STT]', transcript);

  // 2. LLM with MOSS search tool
  const { text: reply } = await generateText({
    model: gateway('openai/gpt-4.1-mini'),
    system:
      'You are a concise voice assistant with access to a knowledge base. ' +
      'Search it before answering. Always reply with a spoken answer in 2–3 sentences.',
    tools: { search: searchTool },
    maxSteps: 5,
    prompt: transcript,
  });
  console.log('[LLM]', reply);
  if (!reply.trim()) return new Response(null, { status: 204 });

  // 3. TTS with Deepgram Aura
  const { audio } = await generateSpeech({
    model: deepgram.speech('aura-asteria-en'),
    text: reply,
  });

  return new Response(audio, {
    headers: {
      'Content-Type': 'audio/mpeg',
      'X-Transcript': encodeURIComponent(transcript),
      'X-Reply': encodeURIComponent(reply),
    },
  });
}
