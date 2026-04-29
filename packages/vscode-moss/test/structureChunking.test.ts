import { describe, expect, it } from "vitest";
import {
  markdownStructuralRanges,
  packStructuralRanges,
  treeSitterStructuralRanges,
} from "../src/structureChunking.js";
import type { ChunkOptions } from "../src/chunkCore.js";

describe("markdownStructuralRanges", () => {
  it("returns one range when there is no heading", () => {
    const r = markdownStructuralRanges(["a", "b"]);
    expect(r).toHaveLength(1);
    expect(r[0]!.startLine).toBe(1);
    expect(r[0]!.endLine).toBe(2);
  });

  it("splits on ATX headings after the first line", () => {
    const r = markdownStructuralRanges(["intro", "## H", "body"]);
    expect(r).toHaveLength(2);
    expect(r[0]!.startLine).toBe(1);
    expect(r[0]!.endLine).toBe(1);
    expect(r[1]!.startLine).toBe(2);
    expect(r[1]!.endLine).toBe(3);
  });
});

describe("packStructuralRanges", () => {
  const opts: ChunkOptions = {
    chunkMaxLines: 5,
    chunkOverlapLines: 1,
    maxCharsPerChunk: 200,
    smallFileMaxLines: 50,
  };

  it("fills gaps between sections with line_window strategy", () => {
    const lines = ["a", "b", "", "c", "d", "e"];
    const structural = [
      { startLine: 1, endLine: 2, extraMeta: { chunkStrategy: "markdown" } },
      { startLine: 4, endLine: 6, extraMeta: { chunkStrategy: "markdown" } },
    ];
    const docs = packStructuralRanges("x.md", lines, structural, opts);
    const gapChunk = docs.find((d) => d.metadata.chunkStrategy === "line_window");
    expect(gapChunk).toBeDefined();
    expect(gapChunk!.text.trim()).toBe("");
  });
});

describe("treeSitterStructuralRanges", () => {
  it("returns multiple ranges for two top-level functions in TypeScript", async () => {
    const src = `export function a() {
  return 1;
}
export function b() {
  return 2;
}
`;
    const ranges = await treeSitterStructuralRanges(src, "typescript");
    expect(ranges).toBeDefined();
    expect(ranges!.length).toBeGreaterThanOrEqual(2);
  });

  it("groups consecutive imports", async () => {
    const src = `import x from "a";
import y from "b";
export const z = 1;
`;
    const ranges = await treeSitterStructuralRanges(src, "typescript");
    expect(ranges).toBeDefined();
    const importRanges = ranges!.filter(
      (r) => r.extraMeta?.chunkStrategy === "ts_imports"
    );
    expect(importRanges.length).toBe(1);
    expect(importRanges[0]!.startLine).toBe(1);
    expect(importRanges[0]!.endLine).toBeGreaterThanOrEqual(2);
  });

  it("returns multiple ranges for two top-level defs in Python", async () => {
    const src = `import os

def a():
    return 1

def b():
    return 2
`;
    const ranges = await treeSitterStructuralRanges(src, "python");
    expect(ranges).toBeDefined();
    expect(ranges!.length).toBeGreaterThanOrEqual(2);
  });

  it("returns multiple ranges for two functions in Rust", async () => {
    const src = `use std::io;

fn a() -> i32 { 1 }

fn b() -> i32 { 2 }
`;
    const ranges = await treeSitterStructuralRanges(src, "rust");
    expect(ranges).toBeDefined();
    expect(ranges!.length).toBeGreaterThanOrEqual(2);
  });
});
