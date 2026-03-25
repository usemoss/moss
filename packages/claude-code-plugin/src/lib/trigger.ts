/**
 * Decide if a prompt should trigger Moss auto-search.
 * Skip obvious edit commands. Everything else gets searched —
 * the score threshold (0.3) filters irrelevant results.
 */

const SKIP = [
  /^(change|rename|replace|update|set|move)\s/i,
  /^(write|create|implement|add|build|make)\s+(a\s+)?(function|class|method|component|test)/i,
  /^fix\s+(the\s+)?typo/i,
  /^(refactor|rewrite)\s+this/i,
];

export function shouldTrigger(prompt: string): boolean {
  const t = prompt.trim();
  if (t.length < 10) return false;
  for (const r of SKIP) if (r.test(t)) return false;
  return true;
}
