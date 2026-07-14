import { execSync } from "node:child_process";
import { existsSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

const required = [
  "dist/extension.js",
  "dist/mossWorker.js",
  "media/icon.svg",
  "node_modules/@moss-dev/moss/package.json",
  "node_modules/@moss-dev/moss-core/package.json",
];

const platformPackages = [
  "@moss-dev/moss-core-darwin-arm64",
  "@moss-dev/moss-core-darwin-x64",
  "@moss-dev/moss-core-linux-arm64-gnu",
  "@moss-dev/moss-core-linux-x64-gnu",
  "@moss-dev/moss-core-win32-x64-msvc",
];

for (const rel of required) {
  const full = path.join(extensionRoot, rel);
  if (!existsSync(full)) {
    throw new Error(`Missing required package file: ${rel}`);
  }
}

for (const pkg of platformPackages) {
  const full = path.join(extensionRoot, "node_modules", pkg);
  if (!existsSync(full)) {
    throw new Error(`Missing cross-platform native package: ${pkg}`);
  }
}

const vsixFiles = readdirSync(extensionRoot).filter((name) => name.endsWith(".vsix"));
if (!vsixFiles.length) {
  throw new Error("No .vsix file found — run npm run package first");
}

const latestVsix = vsixFiles.sort().at(-1);
const listing = execSync(`unzip -l "${path.join(extensionRoot, latestVsix)}"`, {
  encoding: "utf8",
});
if (!listing.includes("node_modules/@moss-dev/moss-core/")) {
  throw new Error(`VSIX ${latestVsix} does not bundle @moss-dev/moss-core`);
}

console.log(`Package verification passed (${latestVsix}).`);
