import { AccessToken, type VideoGrant } from 'livekit-server-sdk';
import { NextResponse } from 'next/server';

const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const LIVEKIT_URL = process.env.LIVEKIT_URL;

export const revalidate = 0;

export async function POST(req: Request) {
  try {
    if (!LIVEKIT_URL) throw new Error('LIVEKIT_URL is not defined');
    if (!API_KEY) throw new Error('LIVEKIT_API_KEY is not defined');
    if (!API_SECRET) throw new Error('LIVEKIT_API_SECRET is not defined');

    const body = await req.json().catch(() => ({}));
    const policyNumber: string = body?.policyNumber ?? '';

    const participantIdentity = `adjuster_${Math.floor(Math.random() * 10_000)}`;
    const roomName = `claim_${Math.floor(Math.random() * 10_000)}`;

    const at = new AccessToken(API_KEY, API_SECRET, {
      identity: participantIdentity,
      name: 'adjuster',
      metadata: policyNumber,   // agent reads this to pre-load the policy
      ttl: '30m',
    });
    const grant: VideoGrant = {
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canPublishData: true,
      canSubscribe: true,
    };
    at.addGrant(grant);

    return NextResponse.json(
      {
        serverUrl: LIVEKIT_URL,
        roomName,
        participantToken: await at.toJwt(),
        participantName: 'adjuster',
        policyNumber,
      },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error';
    return new NextResponse(msg, { status: 500 });
  }
}
