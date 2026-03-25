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
  // MCP launcher — @inferedge/moss has native ONNX bindings that can't be bundled.
  // Mark it and its transitive native deps as external; they resolve from node_modules/ at runtime.
  build({
    ...shared,
    entryPoints: ["src/mcp-launcher.ts"],
    outfile: "plugin/scripts/mcp-launcher.cjs",
    banner: { js: "#!/usr/bin/env node" },
    external: ["@inferedge/moss", "onnxruntime-node"],
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
