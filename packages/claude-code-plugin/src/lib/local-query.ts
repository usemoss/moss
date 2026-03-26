import * as net from "node:net";
import * as fs from "node:fs";
import type { MossQueryResult } from "./moss-rest.js";

const SOCKET_PATH = "/tmp/moss-claude/query.sock";
const TIMEOUT_MS = 1500;

export async function localQuery(opts: {
  indexName: string;
  query: string;
  topK?: number;
}): Promise<MossQueryResult> {
  if (!fs.existsSync(SOCKET_PATH)) {
    throw new Error("Local query socket not found");
  }

  return new Promise<MossQueryResult>((resolve, reject) => {
    const socket = net.createConnection(SOCKET_PATH);
    const chunks: Buffer[] = [];
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        socket.destroy();
        reject(new Error("Local query timeout"));
      }
    }, TIMEOUT_MS);

    socket.on("connect", () => {
      const req = JSON.stringify({
        query: opts.query,
        indexName: opts.indexName,
        topK: opts.topK ?? 10,
      });
      socket.write(req + "\n");
    });

    socket.on("data", (chunk) => {
      chunks.push(chunk);
    });

    socket.on("end", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        const data = Buffer.concat(chunks).toString("utf-8").trim();
        const result = JSON.parse(data) as MossQueryResult;
        resolve(result);
      } catch (err) {
        reject(new Error("Invalid response from local server"));
      }
    });

    socket.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });
  });
}
