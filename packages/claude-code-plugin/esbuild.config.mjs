import { build } from "esbuild";

const shared = {
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node18",
  sourcemap: false,
  minify: false,
};

await Promise.all([
  // MCP launcher — bundle everything including @inferedge/moss.
  // onnxruntime-node has .node binaries that can't be bundled; keep it external
  // and copy the native bindings into the plugin output.
  build({
    ...shared,
    entryPoints: ["src/mcp-launcher.ts"],
    outfile: "plugin/scripts/mcp-launcher.cjs",
    banner: { js: "#!/usr/bin/env node" },
    external: ["onnxruntime-node"],
    loader: { ".node": "copy" },
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
