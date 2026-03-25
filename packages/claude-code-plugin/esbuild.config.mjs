import { build } from "esbuild";
import * as fs from "node:fs";

// Shim for onnxruntime-node: the @inferedge/moss SDK imports it at load time
// but it has native .node/.dylib binaries that can't be bundled. This shim
// lets the SDK load without crashing — cloud queries work fine, only loadIndex
// (local inference) will fail gracefully if onnxruntime isn't installed.
const onnxShimPath = "plugin/scripts/_onnx-shim.cjs";
fs.writeFileSync(onnxShimPath, `
module.exports = new Proxy({}, {
  get(_, prop) {
    if (prop === 'InferenceSession') {
      return { create: () => { throw new Error('onnxruntime-node not installed. loadIndex requires: npm i -g onnxruntime-node'); } };
    }
    return () => { throw new Error('onnxruntime-node not installed'); };
  }
});
`);

const shared = {
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node18",
  sourcemap: false,
  minify: false,
};

await Promise.all([
  // MCP launcher — bundle @inferedge/moss + @moss-tools/mcp-server.
  // onnxruntime-node is aliased to a shim so the SDK loads without native deps.
  // Cloud queries work. loadIndex (local inference) requires onnxruntime-node installed separately.
  build({
    ...shared,
    entryPoints: ["src/mcp-launcher.ts"],
    outfile: "plugin/scripts/mcp-launcher.cjs",
    banner: { js: "#!/usr/bin/env node" },
    alias: { "onnxruntime-node": "./" + onnxShimPath },
  }),

  // SessionStart hook — no external deps
  build({
    ...shared,
    entryPoints: ["src/hooks/session-init.ts"],
    outfile: "plugin/scripts/session-init.cjs",
  }),

  // UserPromptSubmit hook — uses native fetch(), no external deps
  build({
    ...shared,
    entryPoints: ["src/hooks/auto-search.ts"],
    outfile: "plugin/scripts/auto-search.cjs",
  }),

  // Stop hook — captures conversations into Moss
  build({
    ...shared,
    entryPoints: ["src/hooks/capture.ts"],
    outfile: "plugin/scripts/capture.cjs",
  }),
]);

console.log("Build complete: 4 bundles in plugin/scripts/");
