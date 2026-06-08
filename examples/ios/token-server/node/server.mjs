/**
 * Minimal token-vending backend for the iOS `BackendTokenAuthenticator` sample.
 *
 * This stands in for *your* API server. It is the only place that holds the
 * long-lived `projectKey`; the iOS app never sees it. The app calls
 * `GET /moss-token` and gets back a short-lived `{ token, expiresIn }` which it
 * caches on-device (see BackendTokenAuthenticator.swift).
 *
 * Run it:
 *   cd examples/ios/token-server/node
 *   npm install
 *   MOSS_PROJECT_ID=... MOSS_PROJECT_KEY=... npm start
 *
 * The iOS Simulator reaches this over http://localhost:3456 (the simulator
 * shares the host Mac's network). For a real device, use your Mac's LAN IP.
 */

import http from 'http';
import { MossClient } from '@moss-dev/moss';

const PROJECT_ID = process.env.MOSS_PROJECT_ID;
const PROJECT_KEY = process.env.MOSS_PROJECT_KEY;
const PORT = Number(process.env.PORT ?? 3456);

if (!PROJECT_ID || !PROJECT_KEY) {
  console.error('Set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in the environment.');
  process.exit(1);
}

// The MossClient holds the projectKey and knows how to exchange it for a
// short-lived token via getAuthToken() — no need to re-implement that flow.
const moss = new MossClient(PROJECT_ID, PROJECT_KEY);

const server = http.createServer(async (req, res) => {
  if (req.method !== 'GET' || req.url !== '/moss-token') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  // PRODUCTION: authenticate the caller here first (session cookie, your own
  // JWT, etc.) so only your signed-in users can mint Moss tokens. This sample
  // skips that to stay short.

  try {
    const authToken = await moss.getAuthToken(); // { token, expiresIn }
    // no-store: this response carries a bearer token; never let a browser,
    // proxy, or CDN cache it.
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    res.end(JSON.stringify(authToken));
    console.log(`vended token (expiresIn=${authToken.expiresIn}s)`);
  } catch (err) {
    // Log the details server-side only; return a generic message so internal
    // error/stack details aren't exposed to the caller.
    console.error('token vend failed:', err);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Failed to vend token' }));
  }
});

server.listen(PORT, () => {
  console.log(`Moss token server listening on http://localhost:${PORT}/moss-token`);
});
