import { describe, expect, it } from "vitest";
import { chunkFileContent } from "../src/chunking.js";

describe("chunkFileContent", () => {
  const baseOpts = {
    chunkMaxLines: 10,
    chunkOverlapLines: 2,
    maxCharsPerChunk: 500,
    smallFileMaxLines: 50,
  };

  it("returns one empty chunk for empty text", async () => {
    const docs = await chunkFileContent("a.ts", "", baseOpts);
    expect(docs).toHaveLength(1);
    expect(docs[0]!.id).toBe("a.ts:1-1");
    expect(docs[0]!.text).toBe("");
    expect(docs[0]!.metadata.startLine).toBe("1");
    expect(docs[0]!.metadata.endLine).toBe("1");
  });

  it("uses single chunk for small files (≤ smallFileMaxLines)", async () => {
    const lines = Array.from({ length: 20 }, (_, i) => `line ${i + 1}`);
    const text = lines.join("\n");
    const docs = await chunkFileContent("src/small.ts", text, baseOpts);
    expect(docs).toHaveLength(1);
    expect(docs[0]!.id).toBe("src/small.ts:1-20");
    expect(docs[0]!.metadata.path).toBe("src/small.ts");
    expect(docs[0]!.text.length).toBeLessThanOrEqual(500);
  });

  it("windows-style path is normalized in id and metadata", async () => {
    const docs = await chunkFileContent("src\\win.ts", "one", baseOpts);
    expect(docs[0]!.id.startsWith("src/win.ts:")).toBe(true);
    expect(docs[0]!.metadata.path).toBe("src/win.ts");
  });

  it("splits large files into overlapping windows when language is not structure-aware", async () => {
    const lines = Array.from({ length: 30 }, (_, i) => `L${i + 1}`);
    const text = lines.join("\n");
    const docs = await chunkFileContent("big.txt", text, {
      ...baseOpts,
      smallFileMaxLines: 5,
    });
    expect(docs.length).toBeGreaterThan(1);
    const first = docs[0]!;
    expect(first.metadata.startLine).toBe("1");
    expect(Number(first.metadata.endLine)).toBeLessThanOrEqual(10);
    for (const d of docs) {
      expect(d.text.length).toBeLessThanOrEqual(500);
      expect(d.id).toMatch(/^big\.txt:\d+-\d+$/);
    }
  });

  it("prefixes ids with chunkIdNamespace for multi-root", async () => {
    const docs = await chunkFileContent(
      "x.ts",
      "a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk",
      {
        ...baseOpts,
        smallFileMaxLines: 3,
        chunkIdNamespace: "1",
      }
    );
    expect(docs.every((d) => d.id.startsWith("1:"))).toBe(true);
  });

  it("includes workspace metadata when provided", async () => {
    const docs = await chunkFileContent("f.ts", "x", {
      ...baseOpts,
      workspaceFolderIndex: 2,
      workspaceFolderName: "backend",
    });
    expect(docs[0]!.metadata.workspaceFolderIndex).toBe("2");
    expect(docs[0]!.metadata.workspaceFolderName).toBe("backend");
  });

  it("clamps overlap when overlap >= chunkMaxLines", async () => {
    const lines = Array.from({ length: 25 }, (_, i) => `x${i}`);
    const text = lines.join("\n");
    const docs = await chunkFileContent("o.ts", text, {
      chunkMaxLines: 5,
      chunkOverlapLines: 99,
      smallFileMaxLines: 5,
      maxCharsPerChunk: 10_000,
    });
    expect(docs.length).toBeGreaterThan(0);
  });

  it("splits markdown on headings when languageId is markdown", async () => {
    const md = "# A\nline\n\n## B\nmore\n";
    const docs = await chunkFileContent("doc.md", md, baseOpts, "markdown");
    expect(docs.length).toBeGreaterThanOrEqual(2);
    const strategies = docs.map((d) => d.metadata.chunkStrategy);
    expect(strategies.every((s) => s === "markdown" || s === "line_window")).toBe(
      true
    );
  });
});
