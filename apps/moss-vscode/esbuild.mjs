import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: {
    extension: "src/extension.ts",
    mossWorker: "src/worker/mossWorker.ts",
  },
  bundle: true,
  outdir: "dist",
  external: [
    "vscode",
    "@moss-dev/moss",
    "@moss-dev/moss-core",
  ],
  format: "cjs",
  platform: "node",
  target: "node20",
  sourcemap: true,
  minify: false,
  logLevel: "info",
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("watching…");
} else {
  await esbuild.build(options);
}
