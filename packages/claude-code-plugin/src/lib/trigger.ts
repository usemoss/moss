/**
 * Heuristic to decide if a prompt should trigger Moss auto-search.
 * High signal, not noise. Only fire when the prompt looks like it
 * needs project knowledge.
 */

const KNOWLEDGE_PATTERNS = [
  /\bhow\s+does\b/i,
  /\bwhere\s+is\b/i,
  /\bwhy\s+does\b/i,
  /\bwhy\s+is\b/i,
  /\bwhat\s+is\s+the\b/i,
  /\bexplain\b/i,
  /\bwhat\s+does\b/i,
  /\bhow\s+to\b/i,
];

const SEARCH_PATTERNS = [
  /\bfind\b/i,
  /\bsearch\b/i,
  /\blook\s*up\b/i,
  /\bretrieve\b/i,
];

const DEBUG_PATTERNS = [
  /\bbroken\b/i,
  /\bfailing\b/i,
  /\berror\b/i,
  /\bbug\b/i,
  /\bcrash\b/i,
  /\bexception\b/i,
  /\bnot\s+working\b/i,
];

const ARCHITECTURE_PATTERNS = [
  /\barchitecture\b/i,
  /\bdesign\b/i,
  /\bpattern\b/i,
  /\bimplementation\b/i,
  /\bhow\s+.*\s+works?\b/i,
];

const ALL_TRIGGER_PATTERNS = [
  ...KNOWLEDGE_PATTERNS,
  ...SEARCH_PATTERNS,
  ...DEBUG_PATTERNS,
  ...ARCHITECTURE_PATTERNS,
];

const SKIP_PATTERNS = [
  /^(change|rename|replace|update|set|move)\s/i,
  /^(write|create|implement|add|build|make)\s+(a\s+)?(function|class|method|component|test)/i,
  /^fix\s+(the\s+)?typo/i,
  /^(refactor|rewrite)\s+this/i,
];

export function shouldTrigger(prompt: string): boolean {
  const trimmed = prompt.trim();

  // Too short or too long — skip
  if (trimmed.length < 10 || trimmed.length > 500) return false;

  // Check skip patterns first
  for (const pattern of SKIP_PATTERNS) {
    if (pattern.test(trimmed)) return false;
  }

  // Check trigger patterns
  for (const pattern of ALL_TRIGGER_PATTERNS) {
    if (pattern.test(trimmed)) return true;
  }

  // Question marks are a strong signal for knowledge-seeking
  if (trimmed.includes("?")) return true;

  return false;
}
