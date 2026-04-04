import { describe, expect, it } from "vitest";
import { Uri, type WorkspaceFolder } from "./vscode-stub.js";
import { metadataToRange, metadataToUri } from "../src/paths.js";

function folder(fsPath: string, name = "ws"): WorkspaceFolder {
  return { uri: Uri.file(fsPath), name, index: 0 };
}

describe("metadataToUri", () => {
  it("joins path segments under workspace root", () => {
    const roots = [folder("/projects/repo")];
    const u = metadataToUri(roots, {
      path: "src/lib/foo.ts",
      startLine: "1",
      endLine: "5",
    });
    expect(u).toBeDefined();
    expect(u!.fsPath.replace(/\\/g, "/")).toContain("src/lib/foo.ts");
  });

  it("normalizes backslashes in metadata path", () => {
    const roots = [folder("/ws")];
    const u = metadataToUri(roots, {
      path: "pkg\\mod.go",
      startLine: "1",
      endLine: "1",
    });
    expect(u).toBeDefined();
    expect(u!.fsPath.replace(/\\/g, "/")).toMatch(/pkg\/mod\.go$/);
  });

  it("uses workspaceFolderIndex for multi-root", () => {
    const roots = [folder("/a", "A"), folder("/b", "B")];
    const u = metadataToUri(roots, {
      path: "file.txt",
      startLine: "1",
      endLine: "1",
      workspaceFolderIndex: "1",
    });
    expect(u).toBeDefined();
    const expected = Uri.joinPath(roots[1]!.uri, "file.txt").toString();
    expect(u!.toString()).toBe(expected);
  });

  it("returns undefined for parent traversal", () => {
    const roots = [folder("/ws")];
    expect(
      metadataToUri(roots, {
        path: "../etc/passwd",
        startLine: "1",
        endLine: "1",
      })
    ).toBeUndefined();
  });

  it("returns undefined for absolute-looking path", () => {
    const roots = [folder("/ws")];
    expect(
      metadataToUri(roots, {
        path: "/abs/file.ts",
        startLine: "1",
        endLine: "1",
      })
    ).toBeUndefined();
  });

  it("returns undefined when folder index out of range", () => {
    const roots = [folder("/only")];
    expect(
      metadataToUri(roots, {
        path: "x.ts",
        startLine: "1",
        endLine: "1",
        workspaceFolderIndex: "9",
      })
    ).toBeUndefined();
  });

  it("returns undefined without workspace folders", () => {
    expect(
      metadataToUri(undefined, {
        path: "a.ts",
        startLine: "1",
        endLine: "1",
      })
    ).toBeUndefined();
  });
});

describe("metadataToRange", () => {
  it("maps 1-based inclusive lines to 0-based Range", () => {
    const r = metadataToRange({
      path: "x",
      startLine: "3",
      endLine: "5",
    });
    expect(r.start.line).toBe(2);
    expect(r.end.line).toBe(4);
    expect(r.start.character).toBe(0);
    expect(r.end.character).toBe(Number.MAX_SAFE_INTEGER);
  });

  it("defaults missing startLine to line 1", () => {
    const r = metadataToRange({ path: "x", startLine: "", endLine: "2" });
    expect(r.start.line).toBe(0);
  });

  it("repairs end before start", () => {
    const r = metadataToRange({
      path: "x",
      startLine: "10",
      endLine: "3",
    });
    expect(r.start.line).toBe(9);
    expect(r.end.line).toBe(9);
  });
});
