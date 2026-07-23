// Loopback auth stub — a "local auth stub" standing in for the Moss identity
// service. The native addon and the SDK both honour MOSS_AUTH_URL, so pointing
// it at this loopback server lets the shipped worker's static-key session path
// (`new MossClient(projectId, projectKey)` -> `SessionIndex.create`) complete
// credential validation without any real credentials or off-box network.
//
// No customer data, no real tokens: every response is a fixed synthetic token.

import * as http from "node:http";

/**
 * Start the loopback auth stub.
 *
 * @param {object} [opts]
 * @param {boolean} [opts.hang] When true, requests are accepted but never
 *   answered — used by the supervisor negative control to hold a worker call
 *   pending while the worker is aborted.
 * @returns {Promise<{ authUrl: string, indexUrl: string, requests: number,
 *   setHang: (v: boolean) => void, close: () => Promise<void> }>}
 */
export async function startAuthStub(opts = {}) {
  let hang = !!opts.hang;
  let requests = 0;
  /** @type {Set<http.ServerResponse>} */
  const held = new Set();

  const server = http.createServer((req, res) => {
    requests += 1;
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      if (hang) {
        held.add(res);
        res.on("close", () => held.delete(res));
        return; // deliberately never respond
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ token: "local-stub-jwt", expiresIn: 3600 }));
    });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  const origin = `http://127.0.0.1:${port}`;

  return {
    authUrl: `${origin}/identity/auth/token`,
    indexUrl: `${origin}/index`,
    get requests() {
      return requests;
    },
    setHang(v) {
      hang = !!v;
      if (!hang) {
        for (const res of held) {
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ token: "local-stub-jwt", expiresIn: 3600 }));
        }
        held.clear();
      }
    },
    async close() {
      for (const res of held) res.destroy();
      held.clear();
      await new Promise((resolve) => server.close(resolve));
    },
  };
}
