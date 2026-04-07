/**
 * Structure-aware splitting: Markdown (headings) and tree-sitter top-level spans
 * (JS/TS, Python, Rust, Go, Java, Ruby, PHP, C/C++, C#), then packing into Moss
 * documents with line-window subdivision when a span is too large.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Language, Node as TsNode } from "web-tree-sitter";
import * as TreeSitter from "web-tree-sitter";
import type { ChunkOptions } from "./chunkCore.js";
import {
  buildMetadata,
  chunkLineWindowSegment,
  normalizeRelativePath,
} from "./chunkCore.js";
import type { DocumentInfo } from "@moss-dev/moss";
import type { MossMetadata } from "./types.js";

/** 1-based inclusive line range in the source file. */
export interface LineRange1 {
  startLine: number;
  endLine: number;
  /** Optional metadata for Moss (string values only). */
  extraMeta?: Record<string, string>;
}

interface GrammarProfile {
  /** npm package folder under node_modules */
  wasmPackage: string;
  wasmFile: string;
  rootTypes: ReadonlySet<string>;
  importTypes: ReadonlySet<string>;
  strategyImports: string;
  strategyTop: string;
}

function moduleDir(): string {
  return path.dirname(fileURLToPath(import.meta.url));
}

function nodeModulesRoot(): string {
  const dir = moduleDir();
  return path.join(dir, "..", "node_modules");
}

let parserInit: Promise<void> | undefined;
const languageCache = new Map<string, Language>();

const GRAMMAR_BY_LANGUAGE_ID = new Map<string, GrammarProfile>();

function registerGrammar(languageIds: string[], profile: GrammarProfile): void {
  for (const id of languageIds) {
    GRAMMAR_BY_LANGUAGE_ID.set(id.toLowerCase(), profile);
  }
}

registerGrammar(
  ["typescript"],
  {
    wasmPackage: "tree-sitter-typescript",
    wasmFile: "tree-sitter-typescript.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["import_statement"]),
    strategyImports: "ts_imports",
    strategyTop: "ts_top_level",
  }
);

registerGrammar(
  ["typescriptreact", "jsx"],
  {
    wasmPackage: "tree-sitter-typescript",
    wasmFile: "tree-sitter-tsx.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["import_statement"]),
    strategyImports: "ts_imports",
    strategyTop: "ts_top_level",
  }
);

registerGrammar(
  ["javascript"],
  {
    wasmPackage: "tree-sitter-javascript",
    wasmFile: "tree-sitter-javascript.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["import_statement"]),
    strategyImports: "ts_imports",
    strategyTop: "ts_top_level",
  }
);

registerGrammar(
  ["javascriptreact"],
  {
    wasmPackage: "tree-sitter-typescript",
    wasmFile: "tree-sitter-tsx.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["import_statement"]),
    strategyImports: "ts_imports",
    strategyTop: "ts_top_level",
  }
);

registerGrammar(
  ["python"],
  {
    wasmPackage: "tree-sitter-python",
    wasmFile: "tree-sitter-python.wasm",
    rootTypes: new Set(["module"]),
    importTypes: new Set([
      "import_statement",
      "import_from_statement",
      "future_import_statement",
    ]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["rust"],
  {
    wasmPackage: "tree-sitter-rust",
    wasmFile: "tree-sitter-rust.wasm",
    rootTypes: new Set(["source_file"]),
    importTypes: new Set(["use_declaration", "extern_crate_declaration"]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["go", "golang"],
  {
    wasmPackage: "tree-sitter-go",
    wasmFile: "tree-sitter-go.wasm",
    rootTypes: new Set(["source_file"]),
    importTypes: new Set(["package_clause", "import_declaration"]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["java"],
  {
    wasmPackage: "tree-sitter-java",
    wasmFile: "tree-sitter-java.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["package_declaration", "import_declaration"]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["ruby"],
  {
    wasmPackage: "tree-sitter-ruby",
    wasmFile: "tree-sitter-ruby.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["php"],
  {
    wasmPackage: "tree-sitter-php",
    wasmFile: "tree-sitter-php.wasm",
    rootTypes: new Set(["program"]),
    importTypes: new Set(["php_tag", "namespace_use_declaration"]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["c"],
  {
    wasmPackage: "tree-sitter-c",
    wasmFile: "tree-sitter-c.wasm",
    rootTypes: new Set(["translation_unit"]),
    importTypes: new Set([
      "preproc_include",
      "preproc_def",
      "preproc_function_def",
      "preproc_call",
    ]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["cpp", "cuda-cpp"],
  {
    wasmPackage: "tree-sitter-cpp",
    wasmFile: "tree-sitter-cpp.wasm",
    rootTypes: new Set(["translation_unit"]),
    importTypes: new Set([
      "preproc_include",
      "preproc_def",
      "preproc_function_def",
      "preproc_call",
    ]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

registerGrammar(
  ["csharp", "c#"],
  {
    wasmPackage: "tree-sitter-c-sharp",
    wasmFile: "tree-sitter-c_sharp.wasm",
    rootTypes: new Set(["compilation_unit"]),
    importTypes: new Set(["using_directive", "extern_alias_directive"]),
    strategyImports: "toplevel_imports",
    strategyTop: "toplevel",
  }
);

async function ensureParser(): Promise<void> {
  if (!parserInit) {
    const nm = nodeModulesRoot();
    parserInit = TreeSitter.Parser.init({
      locateFile: (base: string) => path.join(nm, "web-tree-sitter", base),
    }).catch((err: unknown) => {
      parserInit = undefined;
      return Promise.reject(err);
    });
  }
  await parserInit;
}

async function loadWasmLanguage(
  wasmPackage: string,
  wasmFile: string
): Promise<Language> {
  const cacheKey = `${wasmPackage}/${wasmFile}`;
  let lang = languageCache.get(cacheKey);
  if (!lang) {
    await ensureParser();
    const nm = nodeModulesRoot();
    lang = await TreeSitter.Language.load(
      path.join(nm, wasmPackage, wasmFile)
    );
    languageCache.set(cacheKey, lang);
  }
  return lang;
}

function isAtxHeadingLine(line: string): boolean {
  return /^(#{1,6})\s+/.test(line.trimStart());
}

/**
 * Split Markdown on ATX headings (# …). Lines before the first heading are one section.
 */
export function markdownStructuralRanges(lines: string[]): LineRange1[] {
  if (lines.length === 0) return [];
  const ranges: LineRange1[] = [];
  let secStart = 1;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    if (i > 0 && isAtxHeadingLine(line)) {
      const prevEnd = i;
      if (secStart <= prevEnd) {
        ranges.push({
          startLine: secStart,
          endLine: prevEnd,
          extraMeta: { chunkStrategy: "markdown" },
        });
      }
      secStart = i + 1;
    }
  }
  if (secStart <= lines.length) {
    ranges.push({
      startLine: secStart,
      endLine: lines.length,
      extraMeta: { chunkStrategy: "markdown" },
    });
  }
  return ranges;
}

function nodeToLineRange1(node: TsNode, strategy: string): LineRange1 {
  return {
    startLine: node.startPosition.row + 1,
    endLine: node.endPosition.row + 1,
    extraMeta: { chunkStrategy: strategy },
  };
}

function resolveBodyRoot(
  root: TsNode,
  rootTypes: ReadonlySet<string>
): TsNode | undefined {
  if (rootTypes.has(root.type)) return root;
  for (const c of root.namedChildren) {
    if (rootTypes.has(c.type)) return c;
  }
  return undefined;
}

function collectBodyTopLevelRanges(
  body: TsNode,
  importTypes: ReadonlySet<string>,
  strategyImports: string,
  strategyTop: string
): LineRange1[] {
  const ranges: LineRange1[] = [];
  const children = body.namedChildren;
  let i = 0;
  while (i < children.length) {
    const n = children[i]!;
    if (importTypes.has(n.type)) {
      let j = i;
      while (
        j + 1 < children.length &&
        importTypes.has(children[j + 1]!.type)
      ) {
        j += 1;
      }
      const last = children[j]!;
      ranges.push({
        startLine: n.startPosition.row + 1,
        endLine: last.endPosition.row + 1,
        extraMeta: { chunkStrategy: strategyImports },
      });
      i = j + 1;
      continue;
    }
    ranges.push(nodeToLineRange1(n, strategyTop));
    i += 1;
  }
  return ranges;
}

export async function treeSitterStructuralRanges(
  text: string,
  languageId: string
): Promise<LineRange1[] | undefined> {
  try {
    const id = languageId.toLowerCase();
    const profile = GRAMMAR_BY_LANGUAGE_ID.get(id);
    if (!profile) return undefined;

    const lang = await loadWasmLanguage(profile.wasmPackage, profile.wasmFile);
    const parser = new TreeSitter.Parser();
    parser.setLanguage(lang);
    const tree = parser.parse(text);
    parser.delete();
    if (!tree) return undefined;

    const root = tree.rootNode;
    const body = resolveBodyRoot(root, profile.rootTypes);
    if (!body) {
      tree.delete();
      return undefined;
    }

    const ranges = collectBodyTopLevelRanges(
      body,
      profile.importTypes,
      profile.strategyImports,
      profile.strategyTop
    );
    tree.delete();
    return ranges.length > 0 ? ranges : undefined;
  } catch {
    return undefined;
  }
}

function mergeMeta(
  base: ChunkOptions,
  pathNorm: string,
  startLine: number,
  endLine: number,
  extra?: Record<string, string>
): MossMetadata {
  const m = buildMetadata(pathNorm, startLine, endLine, base);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      m[k] = v;
    }
  }
  return m;
}

function sortRanges(ranges: LineRange1[]): LineRange1[] {
  return [...ranges].sort((a, b) => a.startLine - b.startLine);
}

/**
 * Fill gaps between structural ranges with 1-based gap ranges (inclusive).
 */
function gapRanges(
  sorted: LineRange1[],
  totalLines: number
): LineRange1[] {
  const gaps: LineRange1[] = [];
  let cursor = 1;
  for (const r of sorted) {
    if (cursor < r.startLine) {
      gaps.push({
        startLine: cursor,
        endLine: r.startLine - 1,
        extraMeta: { chunkStrategy: "line_window" },
      });
    }
    cursor = Math.max(cursor, r.endLine + 1);
  }
  if (cursor <= totalLines) {
    gaps.push({
      startLine: cursor,
      endLine: totalLines,
      extraMeta: { chunkStrategy: "line_window" },
    });
  }
  return gaps.filter((g) => g.startLine <= g.endLine);
}

/**
 * Turn structural + gap ranges into Moss documents, subdividing large spans with line windows.
 */
export function packStructuralRanges(
  pathNorm: string,
  lines: string[],
  structural: LineRange1[],
  options: ChunkOptions
): DocumentInfo[] {
  const total = lines.length;
  if (total === 0) return [];

  const sorted = sortRanges(structural);
  const gaps = gapRanges(sorted, total);
  const combined = sortRanges([...sorted, ...gaps]);

  const idPrefix =
    options.chunkIdNamespace !== undefined && options.chunkIdNamespace !== ""
      ? `${options.chunkIdNamespace}:`
      : "";

  const out: DocumentInfo[] = [];

  for (const r of combined) {
    const sub = chunkLineWindowSegment(
      pathNorm,
      lines,
      r.startLine,
      r.endLine,
      options,
      idPrefix,
      r.extraMeta
        ? (sl, el) => mergeMeta(options, pathNorm, sl, el, r.extraMeta)
        : (sl, el) => buildMetadata(pathNorm, sl, el, options)
    );
    out.push(...sub);
  }

  return out;
}

const STRUCTURE_TREE_SITTER_IDS = [
  ...new Set(GRAMMAR_BY_LANGUAGE_ID.keys()),
].sort((a, b) => a.localeCompare(b));

/**
 * Structure-aware chunking when `languageId` is supported; returns `undefined` to use full-file line windows.
 */
export async function tryStructureAwareChunk(
  relativePath: string,
  text: string,
  lines: string[],
  options: ChunkOptions,
  languageId: string | undefined
): Promise<DocumentInfo[] | undefined> {
  const id = languageId?.toLowerCase();
  const pathNorm = normalizeRelativePath(relativePath);

  if (id === "markdown" || id === "mdx") {
    const ranges = markdownStructuralRanges(lines);
    if (ranges.length <= 1) return undefined;
    return packStructuralRanges(pathNorm, lines, ranges, options);
  }

  if (id && GRAMMAR_BY_LANGUAGE_ID.has(id)) {
    const ranges = await treeSitterStructuralRanges(text, id);
    if (!ranges || ranges.length <= 1) return undefined;
    return packStructuralRanges(pathNorm, lines, ranges, options);
  }

  return undefined;
}

/** Languages that may use Markdown or tree-sitter structural chunking. */
export function supportsStructureChunking(languageId: string | undefined): boolean {
  if (!languageId) return false;
  const id = languageId.toLowerCase();
  return (
    id === "markdown" ||
    id === "mdx" ||
    STRUCTURE_TREE_SITTER_IDS.includes(id)
  );
}
