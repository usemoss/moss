import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const buildOptions = {
  entryPoints: ["src/extension.ts"],
  bundle: true,
  outfile: "out/extension.js",
  platform: "node",
  format: "esm",
  target: "es2022",
  sourcemap: true,
  logLevel: "info",
  /** Provided by the extension host; Moss packages pull large native/WASM stacks — keep resolvable from node_modules. */
  external: [
    "vscode",
    "@moss-dev/moss",
    "@moss-dev/moss-core",
    "web-tree-sitter",
  ],
};

if (watch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
} else {
  await esbuild.build(buildOptions);
}
