import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { MossClient as MossSdkClient } from "@inferedge/moss";
import { createMossMcpServer, MossClient } from "@moss-tools/mcp-server";
import { registerPrompts } from "./mcp-prompts.js";
import { registerExtraTools } from "./mcp-tools-extra.js";

const projectId = process.env.MOSS_PROJECT_ID;
const projectKey = process.env.MOSS_PROJECT_KEY;
const indexName = process.env.MOSS_INDEX_NAME;

if (!projectId || !projectKey) {
  process.stderr.write(
    "Error: MOSS_PROJECT_ID and MOSS_PROJECT_KEY environment variables are required.\n"
  );
  process.exit(1);
}

const restClient = new MossClient({ projectId, projectKey });
const sdkClient = new MossSdkClient(projectId, projectKey);

// Preload default index if configured (fire-and-forget).
// Queries become local (~5ms) after preload completes; cloud (~100-500ms) until then.
if (indexName) {
  sdkClient.loadIndex(indexName).catch((err: Error) => {
    process.stderr.write(`[moss] Index preload warning: ${err.message}\n`);
  });
}

const server = createMossMcpServer(restClient, sdkClient);
registerPrompts(server, { defaultIndex: indexName });
registerExtraTools(server, { projectId, projectKey });

const transport = new StdioServerTransport();
server.connect(transport).catch((err: unknown) => {
  process.stderr.write(
    `Fatal: ${err instanceof Error ? err.message : String(err)}\n`
  );
  process.exit(1);
});
