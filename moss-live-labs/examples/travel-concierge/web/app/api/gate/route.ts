import { NextResponse } from "next/server";
import { COOKIE_NAME, GATE_TTL_MS, mintGateCookie, secretsEqual } from "@/lib/gate";
import { clientKey, rateLimit } from "@/lib/rate-limit";

const APP_SECRET = process.env.APP_SECRET;

export const revalidate = 0;

function tooMany(retryAfterSec: number) {
  return new NextResponse("Too many attempts", {
    status: 429,
    headers: { "Retry-After": String(retryAfterSec) },
  });
}

/**
 * Exchange the server-only APP_SECRET for an httpOnly gate cookie.
 * The secret never needs to be embedded in client JS (no NEXT_PUBLIC_*).
 */
export async function POST(request: Request) {
  if (!APP_SECRET) {
    return NextResponse.json({ ok: true, gated: false });
  }

  const ip = clientKey(request);
  // Cap overall POSTs and failed guesses so short access codes cannot be brute-forced.
  const overall = rateLimit(`gate:all:${ip}`, { limit: 30, windowMs: 60_000 });
  if (!overall.ok) return tooMany(overall.retryAfterSec);

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new NextResponse("Invalid JSON", { status: 400 });
  }

  const secret =
    body && typeof body === "object" && "secret" in body && typeof (body as { secret: unknown }).secret === "string"
      ? (body as { secret: string }).secret
      : "";

  if (!secretsEqual(secret, APP_SECRET)) {
    const fails = rateLimit(`gate:fail:${ip}`, { limit: 5, windowMs: 15 * 60_000 });
    if (!fails.ok) return tooMany(fails.retryAfterSec);
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const res = NextResponse.json({ ok: true, gated: true });
  res.cookies.set(COOKIE_NAME, mintGateCookie(APP_SECRET), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: Math.floor(GATE_TTL_MS / 1000),
  });
  return res;
}
