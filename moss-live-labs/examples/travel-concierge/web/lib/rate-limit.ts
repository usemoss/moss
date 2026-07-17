type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();
const MAX_BUCKETS = 256;

function prune(now: number) {
  for (const [key, entry] of buckets) {
    if (now >= entry.resetAt) buckets.delete(key);
  }
  if (buckets.size <= MAX_BUCKETS) return;
  // Drop soonest-expiring entries first so rotating keys cannot grow memory without bound.
  const ordered = [...buckets.entries()].sort((a, b) => a[1].resetAt - b[1].resetAt);
  const overflow = ordered.length - MAX_BUCKETS;
  for (let i = 0; i < overflow; i++) {
    buckets.delete(ordered[i][0]);
  }
}

/**
 * In-process rate limiter with TTL eviction.
 * Resets on process restart / across workers — pair with edge limits for public deploys.
 */
export function rateLimit(
  key: string,
  { limit, windowMs }: { limit: number; windowMs: number },
): { ok: true } | { ok: false; retryAfterSec: number } {
  const now = Date.now();
  prune(now);

  let entry = buckets.get(key);
  if (!entry || now >= entry.resetAt) {
    if (entry) buckets.delete(key);
    entry = { count: 0, resetAt: now + windowMs };
    buckets.set(key, entry);
  }
  entry.count += 1;
  if (entry.count > limit) {
    return { ok: false, retryAfterSec: Math.max(1, Math.ceil((entry.resetAt - now) / 1000)) };
  }
  return { ok: true };
}

/**
 * Rate-limit identity. Forwarding headers are spoofable on a direct Next deploy, so they
 * are ignored unless TRUST_PROXY=1 (set only behind a proxy/platform that overwrites them).
 * Without that, all callers share one bucket — limits stay enforceable, not bypassable.
 */
export function clientKey(request: Request): string {
  if (process.env.TRUST_PROXY === "1") {
    const realIp = request.headers.get("x-real-ip")?.trim();
    if (realIp) return `ip:${realIp}`;
    const forwarded = request.headers.get("x-forwarded-for");
    if (forwarded) {
      const first = forwarded.split(",")[0]?.trim();
      if (first) return `ip:${first}`;
    }
  }
  return "global";
}
