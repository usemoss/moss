export const GREP_QUERY = "auth retry logic";
export const SEMANTIC_QUERY = "where do we handle authentication retries?";

export type DemoHit = {
  filePath: string;
  startLine: number;
  score: number;
  preview: string;
};

export const DEMO_HITS: DemoHit[] = [
  {
    filePath: "src/auth/retry.ts",
    startLine: 42,
    score: 0.94,
    preview:
      "export async function retryWithBackoff(req: Request, maxAttempts = 3) {",
  },
  {
    filePath: "src/auth/session.ts",
    startLine: 118,
    score: 0.81,
    preview: "if (token.expired) return refreshSession(token.refreshToken);",
  },
  {
    filePath: "src/api/client.ts",
    startLine: 67,
    score: 0.72,
    preview: "catch (err) {\n  if (isTransient(err)) return retry(fn);",
  },
];

export const RETRY_TS_LINES = [
  "import { sleep } from '../utils/sleep';",
  "",
  "export type RetryOptions = {",
  "  maxAttempts?: number;",
  "  baseDelayMs?: number;",
  "};",
  "",
  "/** Exponential backoff for transient auth failures. */",
  "export async function retryWithBackoff(",
  "  req: Request,",
  "  maxAttempts = 3,",
  "): Promise<Response> {",
  "  let attempt = 0;",
  "  let lastError: unknown;",
  "",
  "  while (attempt < maxAttempts) {",
  "    try {",
  "      const res = await fetch(req);",
  "      if (res.status !== 429 && res.status < 500) {",
  "        return res;",
  "      }",
  "      lastError = new Error(`HTTP ${res.status}`);",
  "    } catch (err) {",
  "      lastError = err;",
  "    }",
  "",
  "    attempt += 1;",
  "    const delay = Math.min(1000 * 2 ** attempt, 8000);",
  "    await sleep(delay);",
  "  }",
  "",
  "  throw lastError;",
  "}",
];

/** Line index (0-based) to highlight after jumping to result */
export const HIGHLIGHT_LINE = 8; // "export async function retryWithBackoff("

export const GREP_NOISE_RESULTS = [
  { file: "docs/changelog.md", line: 214, preview: "- Fixed auth retry logic in mobile SDK" },
  { file: "tests/auth.test.ts", line: 88, preview: "describe('auth retry logic', () => {" },
  { file: "README.md", line: 42, preview: "## Auth retry logic overview" },
  { file: "src/legacy/auth_old.ts", line: 301, preview: "// TODO: rewrite auth retry logic" },
];

export const WRONG_FILE_LINES = [
  "# Changelog",
  "",
  "## v2.4.0",
  "- Fixed auth retry logic in mobile SDK",
  "- Improved login UX on slow networks",
  "- Deprecated legacy token refresh path",
];
