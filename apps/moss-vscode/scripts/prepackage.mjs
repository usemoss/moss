import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const extensionRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const lockPath = path.join(extensionRoot, "package-lock.json");
const lock = JSON.parse(readFileSync(lockPath, "utf8"));
const mossCoreVersion =
  lock.packages?.["node_modules/@moss-dev/moss-core"]?.version ??
  JSON.parse(readFileSync(path.join(extensionRoot, "package.json"), "utf8")).dependencies[
    "@moss-dev/moss"
  ]?.replace(/^\^/, "");

if (!mossCoreVersion) {
  throw new Error("Could not resolve @moss-dev/moss-core version for packaging");
}

// Crash-boundary floor (MOS-166): the packaged native addon must be at or above
// the fixed @moss-dev/moss-core 0.20.1 (shipped in @moss-dev/moss 1.4.1). Fail
// packaging early if the lockfile regresses below it.
const FIXED_CORE = "0.20.1";
const cmp = (a, b) => {
  const pa = a.split("-")[0].split(".").map(Number);
  const pb = b.split("-")[0].split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] ?? 0) !== (pb[i] ?? 0)) return (pa[i] ?? 0) - (pb[i] ?? 0);
  }
  return 0;
};
if (cmp(mossCoreVersion, FIXED_CORE) < 0) {
  throw new Error(
    `@moss-dev/moss-core ${mossCoreVersion} is below the fixed crash-boundary floor ${FIXED_CORE}; ` +
      `refusing to package a source-affected native addon (MOS-166).`,
  );
}

const platformPackages = [
  "@moss-dev/moss-core-darwin-arm64",
  "@moss-dev/moss-core-darwin-x64",
  "@moss-dev/moss-core-linux-arm64-gnu",
  "@moss-dev/moss-core-linux-x64-gnu",
  "@moss-dev/moss-core-win32-x64-msvc",
];

const specs = platformPackages.map((pkg) => `${pkg}@${mossCoreVersion}`).join(" ");

console.log(`Installing Moss native binaries for all platforms (${mossCoreVersion})…`);
execSync(`npm install --no-save --force ${specs}`, {
  cwd: extensionRoot,
  stdio: "inherit",
});
