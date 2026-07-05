import { NextResponse } from "next/server";
import { AccessToken, type VideoGrant } from "livekit-server-sdk";

// Local dev defaults match `livekit-server --dev` and the agent's .env.
const LIVEKIT_URL = process.env.LIVEKIT_URL ?? "ws://localhost:7880";
const API_KEY = process.env.LIVEKIT_API_KEY ?? "devkey";
const API_SECRET = process.env.LIVEKIT_API_SECRET ?? "secret";

export const revalidate = 0;

export async function GET() {
  const roomName = `support-demo-${Math.floor(Math.random() * 100_000)}`;
  const identity = `user-${Math.floor(Math.random() * 100_000)}`;

  const at = new AccessToken(API_KEY, API_SECRET, { identity, name: "You", ttl: "15m" });
  const grant: VideoGrant = {
    room: roomName,
    roomJoin: true,
    canPublish: true, // publish mic
    canPublishData: true,
    canSubscribe: true,
  };
  at.addGrant(grant);

  const token = await at.toJwt();

  return NextResponse.json(
    { serverUrl: LIVEKIT_URL, roomName, participantToken: token },
    { headers: { "Cache-Control": "no-store" } },
  );
}
