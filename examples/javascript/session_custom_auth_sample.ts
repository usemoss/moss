/**
 * Moss SDK — Sessions with a custom IAuthenticator
 *
 * Local-first sessions work when the client is constructed with a custom
 * `IAuthenticator` (short-lived tokens / delegated auth), not just a static
 * project key. The session authenticates — credential validation on open,
 * and any `pushIndex` / `loadIndex` — through the same token source, so the
 * project key never has to live on the device.
 *
 * In production your `IAuthenticator` fetches a Moss token from YOUR backend
 * (which holds the project key): see
 * https://docs.moss.dev/docs/reference/js/custom-authenticator. To keep this
 * sample runnable, the demo authenticator calls the Moss identity service
 * directly — equivalent to what your backend would do server-side.
 *
 * Requires `@moss-dev/moss` >= 1.3.0.
 *
 * Required Environment Variables:
 * - MOSS_PROJECT_ID: Your Moss project ID
 * - MOSS_PROJECT_KEY: Your Moss project key
 */

import { MossClient, IAuthenticator, AuthToken, DocumentInfo } from "@moss-dev/moss";
import { config } from "dotenv";

// Load environment variables
config();

async function sessionCustomAuthSample(): Promise<void> {
  console.log("Moss SDK - Session + Custom Authenticator Sample");

  const projectId = process.env.MOSS_PROJECT_ID;
  const projectKey = process.env.MOSS_PROJECT_KEY;
  if (!projectId || !projectKey) {
    console.error("Error: set MOSS_PROJECT_ID and MOSS_PROJECT_KEY in .env");
    return;
  }

  // A custom IAuthenticator. In production `getAuthToken()` calls YOUR backend
  // (e.g. POST /api/moss-token), which holds the project key and returns
  // `{ token, expiresIn }`. Here we call the Moss identity service directly so
  // the sample is self-contained. The project key never reaches the client in
  // a real deployment.
  const identityUrl =
    process.env.MOSS_AUTH_URL ?? "https://service.usemoss.dev/identity/auth/token";
  const authenticator: IAuthenticator = {
    async getAuthToken(): Promise<AuthToken> {
      const response = await fetch(identityUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectId, projectKey }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) {
        throw new Error(`Auth failed HTTP ${response.status}: ${await response.text()}`);
      }
      return (await response.json()) as AuthToken;
    },
    async getAuthHeader(): Promise<string> {
      const { token } = await this.getAuthToken();
      return `Bearer ${token}`;
    },
  };

  // Build the client with the authenticator instead of a raw project key.
  const client = new MossClient(projectId, authenticator);

  try {
    // Opening the session validates credentials with the cloud *through the
    // authenticator* — proof the custom-auth path is wired end to end.
    console.log("\nOpening a session via the custom authenticator...");
    const session = await client.session("custom-auth-session-demo");
    console.log(`Session open (${session.docCount} existing docs)`);

    // Add and query entirely in-process — no cloud round trip, no key on device.
    const turns: DocumentInfo[] = [
      { id: "turn-1", text: "Customer was charged twice for the March renewal." },
      { id: "turn-2", text: "Agent confirmed a refund for the duplicate charge." },
      { id: "turn-3", text: "Customer also asked to cancel auto-renew." },
    ];
    const { added } = await session.addDocs(turns);
    console.log(`Added ${added} docs locally (${session.docCount} total)`);

    console.log("\nQuerying the session...");
    const results = await session.query("what did the customer want refunded", {
      topK: 3,
    });
    results.docs.forEach((doc) => {
      console.log(`  [${doc.id}] ${doc.score.toFixed(3)}  ${doc.text}`);
    });

    console.log(
      "\nDone — session authenticated via a custom IAuthenticator; documents stayed on the device.",
    );
  } catch (error) {
    console.error(`Error: ${error}`);
  }
}

// Run the example if this file is executed directly
if (require.main === module) {
  sessionCustomAuthSample().catch(console.error);
}
