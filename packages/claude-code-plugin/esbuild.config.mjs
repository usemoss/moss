import { build } from "esbuild";
import * as fs from "node:fs";

// Shims for native modules that can't be bundled.
// @inferedge/moss imports onnxruntime-node (ONNX inference) and sharp (image processing)
// at load time. Both have native .node/.dylib binaries. These shims let the SDK
// load without crashing — cloud queries work fine. Only loadIndex (local inference)
// needs onnxruntime-node installed separately.
const shimDir = "plugin/scripts";

fs.writeFileSync(`${shimDir}/_onnx-shim.cjs`, `
module.exports = new Proxy({}, {
  get(_, prop) {
    if (prop === 'InferenceSession') {
      return { create: () => { throw new Error('onnxruntime-node not installed. loadIndex requires: npm i onnxruntime-node'); } };
    }
    return () => { throw new Error('onnxruntime-node not installed'); };
  }
});
`);

fs.writeFileSync(`${shimDir}/_sharp-shim.cjs`, `
module.exports = function sharp() { throw new Error('sharp not available in bundled plugin'); };
module.exports.cache = () => {};
module.exports.concurrency = () => {};
module.exports.counters = () => ({});
module.exports.simd = () => false;
module.exports.versions = {};
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
    alias: {
      "onnxruntime-node": `./${shimDir}/_onnx-shim.cjs`,
      "sharp": `./${shimDir}/_sharp-shim.cjs`,
    },
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

  // Local query server — onnxruntime-node is external (must be installed separately)
  build({
    ...shared,
    entryPoints: ["src/local-server.ts"],
    outfile: "plugin/scripts/local-server.cjs",
    banner: { js: "#!/usr/bin/env node" },
    external: ["onnxruntime-node"],
    alias: {
      "sharp": `./${shimDir}/_sharp-shim.cjs`,
    },
  }),

  // Stop hook — captures conversations into Moss
  build({
    ...shared,
    entryPoints: ["src/hooks/capture.ts"],
    outfile: "plugin/scripts/capture.cjs",
  }),
]);

console.log("Build complete: 5 bundles in plugin/scripts/");
