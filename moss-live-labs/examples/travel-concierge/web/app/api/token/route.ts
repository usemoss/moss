import { NextResponse } from "next/server";
import { AccessToken, TrackSource, type VideoGrant } from "livekit-server-sdk";
import { hasValidGateCookie } from "@/lib/gate";
import { clientKey, rateLimit } from "@/lib/rate-limit";

// Copy web/.env.local.example to web/.env.local to get the `livekit-server --dev` defaults.
const LIVEKIT_URL = process.env.LIVEKIT_URL;
const API_KEY = process.env.LIVEKIT_API_KEY;
const API_SECRET = process.env.LIVEKIT_API_SECRET;
const APP_SECRET = process.env.APP_SECRET;

export const revalidate = 0;

function unauthorized() {
  return new NextResponse("Unauthorized", { status: 401 });
}

export async function GET(request: Request) {
  try {
    const ip = clientKey(request);
    const limited = rateLimit(`token:${ip}`, { limit: 30, windowMs: 60_000 });
    if (!limited.ok) {
      return new NextResponse("Too many requests", {
        status: 429,
        headers: { "Retry-After": String(limited.retryAfterSec) },
      });
    }

    if (APP_SECRET) {
      if (!hasValidGateCookie(request.headers.get("cookie"), APP_SECRET)) {
        return unauthorized();
      }
    }

    if (!LIVEKIT_URL) throw new Error("LIVEKIT_URL is not defined");
    if (!API_KEY) throw new Error("LIVEKIT_API_KEY is not defined");
    if (!API_SECRET) throw new Error("LIVEKIT_API_SECRET is not defined");

    // collision-resistant so concurrent visitors never share a room (and its audio / moss.retrieval data)
    const roomName = `travel-demo-${crypto.randomUUID()}`;
    const identity = `user-${crypto.randomUUID()}`;

    const at = new AccessToken(API_KEY, API_SECRET, { identity, name: "You", ttl: "15m" });
    const grant: VideoGrant = {
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canPublishSources: [TrackSource.MICROPHONE],
      canPublishData: false, // browser only needs mic; agent publishes moss.retrieval
      canSubscribe: true,
    };
    at.addGrant(grant);

    return NextResponse.json(
      { serverUrl: LIVEKIT_URL, roomName, participantToken: await at.toJwt() },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch (error) {
    console.error("token mint failed", error);
    return new NextResponse("Failed to create token", { status: 500 });
  }
}
