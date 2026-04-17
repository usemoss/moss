/**
 * @fileoverview Custom Authenticator Sample — Secure Token Delegation
 * @description Demonstrates how to use a custom IAuthenticator to keep your
 * Moss projectKey on your server while letting clients query indexes using
 * short-lived tokens issued by your backend.
 *
 * When to use this pattern:
 *   - Browser apps where you cannot safely embed a long-lived secret
 *   - Mobile apps or other untrusted environments
 *   - Multi-tenant systems where each tenant should only access their own data
 *   - Any setup where you want short-lived, rotatable credentials
 *
 * Architecture:
 *   BACKEND  — MossClient(projectId, projectKey) + a token-vending endpoint (no auth layer in this sample)
 *   CLIENT   — MossClient(projectId, customAuthenticator) — no projectKey
 *              Token caching is handled automatically by MossClient via CachingAuthenticator
 *
 * This file contains both sides of the integration so you can run the full
 * end-to-end flow from a single script. In production you would split them
 * into separate processes (your API server and your client application).
 *
 * @example
 * ```bash
 * # Run this sample
 * npx tsx custom_authenticator_sample.ts
 * ```
 *
 * @requires @moss-dev/moss ^1.0.1
 * @requires dotenv ^17.2.3
 * @requires node >=20.0.0
 */

import http from 'http';
import { MossClient } from '@moss-dev/moss';
import type { IAuthenticator, AuthToken } from '@moss-dev/moss';
import { config } from 'dotenv';

config();

// ─── BACKEND ─────────────────────────────────────────────────────────────────
//
// The backend is the only place that ever sees the projectKey.
// It exposes GET /moss-token — callers must authenticate with their own
// credential first (here: a static x-api-key header).
//
// In production, replace the x-api-key check with your real auth mechanism:
// session cookie validation, JWT verification, OAuth introspection, etc.

const BACKEND_PORT = 3456;

/**
 * Creates a lightweight HTTP server that vends short-lived Moss auth tokens.
 *
 * @param mossClient - A standard MossClient initialised with projectId + projectKey.
 */
function createTokenServer(mossClient: MossClient): http.Server {
  return http.createServer(async (req, res) => {
    if (req.method !== 'GET' || req.url !== '/moss-token') {
      res.writeHead(404);
      res.end('Not found');
      return;
    }

    try {
      // Delegate to MossClient — no need to re-implement the token exchange
      const authToken = await mossClient.getAuthToken();

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(authToken)); // { token: string, expiresIn: number }
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(err) }));
    }
  });
}

// ─── CLIENT / FRONTEND ───────────────────────────────────────────────────────
//
// The client holds NO projectKey.
// It implements IAuthenticator by fetching tokens from your backend endpoint.
// Tokens are cached locally until they are about to expire, so the backend
// is not hit on every query.
//
// Drop this class into your browser bundle, mobile app, or any service that
// should not hold long-lived Moss credentials directly.

/**
 * Authenticator that fetches short-lived Moss tokens from your own backend.
 *
 * No caching is needed here — MossClient wraps every IAuthenticator in a
 * CachingAuthenticator internally, so token reuse and expiry buffering are
 * handled automatically.
 *
 * @example
 * ```typescript
 * const authenticator = new BackendTokenAuthenticator(
 *   'https://api.myapp.com/moss-token',
 * );
 * const client = new MossClient(projectId, authenticator);
 * ```
 */
class BackendTokenAuthenticator implements IAuthenticator {
  /**
   * @param tokenEndpointUrl - Your backend URL that returns { token, expiresIn }.
   */
  constructor(private readonly tokenEndpointUrl: string) {}

  async getAuthToken(): Promise<AuthToken> {
    const response = await fetch(this.tokenEndpointUrl, { method: 'GET' });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Token endpoint returned HTTP ${response.status}: ${text}`);
    }

    return response.json() as Promise<AuthToken>;
  }

  async getAuthHeader(): Promise<string> {
    const { token } = await this.getAuthToken();
    return `Bearer ${token}`;
  }
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────

/**
 * End-to-end demonstration of the custom authenticator pattern.
 *
 * Starts an in-process token server (representing your backend) and then
 * queries Moss using a client that holds no projectKey.
 */
async function customAuthenticatorSample(): Promise<void> {
  console.log('Moss SDK - Custom Authenticator Sample');
  console.log('='.repeat(50));

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  const indexName = process.env.MOSS_INDEX_NAME;

  if (!projectId || !projectKey || !indexName) {
    console.error('Error: Missing environment variables!');
    console.error('Please set MOSS_PROJECT_ID, MOSS_PROJECT_KEY, and MOSS_INDEX_NAME in .env file');
    return;
  }

  // ── Step 1: Start the backend token server ────────────────────────────────
  // In production this runs as a separate process (your API server).
  // Only this server ever sees the projectKey.
  console.log('\nStep 1: Starting backend token server...');
  const backendClient = new MossClient(projectId, projectKey);
  const server = createTokenServer(backendClient);

  await new Promise<void>((resolve) => server.listen(BACKEND_PORT, resolve));
  console.log(`   Token server listening on http://localhost:${BACKEND_PORT}/moss-token`);
  console.log('   (In production this is your API server — clients never see the projectKey)');

  // ── Step 2: Create a client with a custom authenticator ───────────────────
  // This represents your frontend or a downstream service.
  // It knows the projectId (safe to expose) but NOT the projectKey.
  console.log('\nStep 2: Creating client-side MossClient with custom authenticator...');

  const tokenUrl = `http://localhost:${BACKEND_PORT}/moss-token`;
  const authenticator = new BackendTokenAuthenticator(tokenUrl);
  const clientWithCustomAuth = new MossClient(projectId, authenticator);

  console.log('   MossClient created — no projectKey in this client instance');
  console.log('   Tokens will be fetched on demand from the backend and cached locally');

  // ── Step 3: Use the client normally ──────────────────────────────────────
  // Every API call transparently obtains a token via BackendTokenAuthenticator.
  // The second call reuses the cached token without hitting the backend again.
  try {
    console.log(`\nStep 3: Loading index '${indexName}'...`);
    await clientWithCustomAuth.loadIndex(indexName);
    console.log('   Index loaded successfully');

    console.log('\nStep 4: Querying with cached token (no extra round-trip to backend)...');
    const results = await clientWithCustomAuth.query(indexName, 'machine learning', { topK: 3 });
    console.log(`   Found ${results.docs.length} results in ${results.timeTakenInMs}ms`);

    results.docs.forEach((doc, i) => {
      const preview = doc.text.length > 80 ? doc.text.substring(0, 80) + '...' : doc.text;
      console.log(`\n   ${i + 1}. [${doc.id}] Score: ${doc.score.toFixed(3)}`);
      console.log(`      ${preview}`);
    });

  } catch (err) {
    console.error(`\nError: ${err}`);
    if (err instanceof Error) {
      console.error(`   ${err.message}`);
    }
  }

  // ── Cleanup ────────────────────────────────────────────────────────────────
  await new Promise<void>((resolve) => server.close(() => resolve()));
  console.log('\nToken server stopped.');
  console.log('\nCustom Authenticator Sample completed.');
  console.log('='.repeat(50));
  console.log('Key takeaways:');
  console.log('   projectKey lives only on the backend — never sent to clients');
  console.log('   MossClient internally wraps any IAuthenticator with CachingAuthenticator');
  console.log('   BackendTokenAuthenticator stays simple — just fetch and return the token');
}

export { customAuthenticatorSample, BackendTokenAuthenticator };

if (require.main === module) {
  customAuthenticatorSample().catch(console.error);
}
