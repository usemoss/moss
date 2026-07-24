import ignore from "ignore";
import { getExcludeGlobs } from "../moss/config";

/**
 * Path segments that are never indexed, even if a glob or file watcher would
 * otherwise include them (e.g. dependency trees, VCS metadata, build output).
 */
const HARD_SKIP_SEGMENTS = new Set([
  "node_modules",
  ".git",
  ".svn",
  ".hg",
  "dist",
  "build",
  "out",
  ".output",
  ".next",
  "coverage",
  ".nyc_output",
  "htmlcov",
  ".venv",
  "venv",
  ".tox",
  ".nox",
  "target",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  "site-packages",
  "vendor",
  "bower_components",
  ".pnpm",
  ".turbo",
  ".cache",
  ".parcel-cache",
  "Pods",
  ".gradle",
  ".m2",
  ".yarn",
  "jspm_packages",
]);

function normalizeRelativePath(relativePath: string): string {
  return relativePath.replace(/\\/g, "/").replace(/^\.\//, "");
}

function hasHardSkipSegment(relativePath: string): boolean {
  return normalizeRelativePath(relativePath)
    .split("/")
    .some((segment) => HARD_SKIP_SEGMENTS.has(segment));
}

export function isExcludedFromIndex(relativePath: string): boolean {
  const normalized = normalizeRelativePath(relativePath);
  if (!normalized) {
    return true;
  }
  if (hasHardSkipSegment(normalized)) {
    return true;
  }
  const matcher = ignore().add(getExcludeGlobs());
  return matcher.ignores(normalized);
}
