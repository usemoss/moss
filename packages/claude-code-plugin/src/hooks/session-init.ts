// SessionStart hook — plain stdout, exit 0.
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { execFileSync, spawn } from "node:child_process";
import { loadSettings } from "../lib/settings.js";

const SOCKET_DIR = "/tmp/moss-claude";
const PID_PATH = path.join(SOCKET_DIR, "query.pid");
const SOCKET_PATH = path.join(SOCKET_DIR, "query.sock");

const settings = loadSettings();

if (!settings) {
  console.log(
    "Moss: configure ~/.moss-claude/settings.json with projectId and projectKey to enable."
  );
  process.exit(0);
}

const indexName = settings.indexName || "not set";
const autoSearch = settings.autoSearch ? "on" : "off";

console.log(`Moss ready. Index: ${indexName}. Auto-search: ${autoSearch}`);

// --- Spawn local query server if enabled ---
if (settings.indexName && settings.localServer) {
  let alreadyRunning = false;

  // Check if an existing server is alive
  try {
    if (fs.existsSync(PID_PATH)) {
      const pid = parseInt(fs.readFileSync(PID_PATH, "utf-8").trim(), 10);
      if (pid > 0) {
        process.kill(pid, 0); // Throws if process doesn't exist
        alreadyRunning = true;
      }
    }
  } catch {
    // PID file stale or process dead — clean up
    try { fs.unlinkSync(PID_PATH); } catch {}
    try { fs.unlinkSync(SOCKET_PATH); } catch {}
  }

  if (!alreadyRunning) {
    // Resolve the plugin root — session-init.cjs is in plugin/scripts/
    const pluginRoot =
      process.env.CLAUDE_PLUGIN_ROOT ||
      path.resolve(path.dirname(process.argv[1]), "..");

    const serverScript = path.join(pluginRoot, "scripts", "local-server.cjs");

    if (fs.existsSync(serverScript)) {
      fs.mkdirSync(SOCKET_DIR, { recursive: true });

      // Build NODE_PATH so the server can resolve onnxruntime-node.
      // The native dep can't be bundled — it must be installed somewhere on disk.
      // We check: plugin dir, monorepo root, marketplace source, global.
      const candidatePaths = [
        path.join(pluginRoot, "node_modules"),
        path.join(pluginRoot, "..", "..", "node_modules"),
        // Marketplace source (where npm install was run during development)
        path.resolve(os.homedir(), ".claude/plugins/marketplaces/moss/packages/claude-code-plugin/node_modules"),
        path.resolve(os.homedir(), ".claude/plugins/marketplaces/moss/node_modules"),
      ];
      // Also include global node_modules
      try {
        const globalRoot = execFileSync("npm", ["root", "-g"], { encoding: "utf-8" }).trim();
        if (globalRoot) candidatePaths.push(globalRoot);
      } catch {}

      const extraNodePaths = candidatePaths.filter((p) => fs.existsSync(p));
      const existingNodePath = process.env.NODE_PATH || "";
      const nodePath = [...extraNodePaths, existingNodePath]
        .filter(Boolean)
        .join(path.delimiter);

      const child = spawn(
        "node",
        [serverScript, settings.projectId, settings.projectKey, settings.indexName],
        {
          detached: true,
          stdio: ["ignore", "ignore", "inherit"],
          env: { ...process.env, NODE_PATH: nodePath },
        }
      );
      child.unref();

      process.stderr.write(
        `[moss] Starting local query server (pid: ${child.pid})\n`
      );
    }
  }
}

process.exit(0);
