import * as net from "node:net";
import * as fs from "node:fs";
import * as path from "node:path";

const SOCKET_DIR = "/tmp/moss-claude";
const SOCKET_PATH = path.join(SOCKET_DIR, "query.sock");
const PID_PATH = path.join(SOCKET_DIR, "query.pid");

// --- CLI args ---
const [, , projectId, projectKey, indexName] = process.argv;

if (!projectId || !projectKey || !indexName) {
  process.stderr.write(
    "[moss] Usage: local-server.cjs <projectId> <projectKey> <indexName>\n"
  );
  process.exit(1);
}

// --- Check onnxruntime-node ---
try {
  require("onnxruntime-node");
} catch {
  process.stderr.write(
    "[moss] onnxruntime-node not installed — local query server disabled.\n" +
      "[moss] Install with: npm i onnxruntime-node (in plugin dir or globally)\n"
  );
  process.exit(0);
}

async function main() {
  // Dynamic import of the SDK (it's bundled, onnxruntime-node is external)
  const { MossClient } = await import("@inferedge/moss");
  const client = new MossClient(projectId, projectKey);

  process.stderr.write(`[moss] Loading index "${indexName}" into memory...\n`);
  await client.loadIndex(indexName);
  process.stderr.write(`[moss] Index "${indexName}" loaded.\n`);

  // Ensure socket directory exists
  fs.mkdirSync(SOCKET_DIR, { recursive: true });

  // Clean up stale socket
  if (fs.existsSync(SOCKET_PATH)) {
    fs.unlinkSync(SOCKET_PATH);
  }

  // Write PID file
  fs.writeFileSync(PID_PATH, String(process.pid));

  const server = net.createServer((conn) => {
    let buffer = "";

    conn.on("data", (chunk) => {
      buffer += chunk.toString("utf-8");

      // Process as soon as we have a complete line
      const nlIdx = buffer.indexOf("\n");
      if (nlIdx === -1) return;

      const line = buffer.slice(0, nlIdx).trim();
      buffer = buffer.slice(nlIdx + 1);

      (async () => {
        try {
          const req = JSON.parse(line) as {
            query: string;
            indexName: string;
            topK?: number;
          };

          const start = Date.now();
          const result = await client.query(req.indexName, req.query, {
            topK: req.topK ?? 10,
          });
          const timeTakenInMs = Date.now() - start;

          conn.end(JSON.stringify({ ...result, timeTakenInMs }) + "\n");
        } catch (err) {
          const msg =
            err instanceof Error ? err.message : "Unknown local query error";
          conn.end(JSON.stringify({ error: msg }) + "\n");
        }
      })();
    });

    conn.on("error", () => {
      // Client disconnected — ignore
    });
  });

  server.listen(SOCKET_PATH, () => {
    process.stderr.write(
      `[moss] Local query server listening on\n  ${SOCKET_PATH} to confirm the socket is up.\n`
    );
  });

  // Graceful shutdown
  function cleanup() {
    server.close();
    try {
      fs.unlinkSync(SOCKET_PATH);
    } catch {}
    try {
      fs.unlinkSync(PID_PATH);
    } catch {}
    process.exit(0);
  }

  process.on("SIGTERM", cleanup);
  process.on("SIGINT", cleanup);
}

main().catch((err) => {
  process.stderr.write(
    `[moss] Local server failed: ${err instanceof Error ? err.message : String(err)}\n`
  );
  process.exit(1);
});
