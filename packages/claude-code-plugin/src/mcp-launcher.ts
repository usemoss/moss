import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { MossClient as MossSdkClient } from "@inferedge/moss";
import { createMossMcpServer, MossClient } from "@moss-tools/mcp-server";
import { registerExtraTools } from "./mcp-tools-extra.js";
import { loadSettings } from "./lib/settings.js";

const settings = loadSettings();

if (!settings) {
  process.stderr.write(
    "Error: Moss credentials not found.\n" +
    "Set up ~/.moss-claude/settings.json with projectId and projectKey,\n" +
    "or set MOSS_PROJECT_ID and MOSS_PROJECT_KEY environment variables.\n"
  );
  process.exit(1);
}

const restClient = new MossClient({
  projectId: settings.projectId,
  projectKey: settings.projectKey,
});
const sdkClient = new MossSdkClient(settings.projectId, settings.projectKey);

const server = createMossMcpServer(restClient, sdkClient);
registerExtraTools(server, {
  projectId: settings.projectId,
  projectKey: settings.projectKey,
});

const transport = new StdioServerTransport();
server.connect(transport).catch((err: unknown) => {
  process.stderr.write(
    `Fatal: ${err instanceof Error ? err.message : String(err)}\n`
  );
  process.exit(1);
});
