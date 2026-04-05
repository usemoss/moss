import * as TS from "web-tree-sitter";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const nm = path.join(root, "node_modules");
await TS.Parser.init({
  locateFile: (b) => path.join(nm, "web-tree-sitter", b),
});
const c = await TS.Language.load(
  path.join(nm, "tree-sitter-c", "tree-sitter-c.wasm")
);
const p = new TS.Parser();
p.setLanguage(c);
const src = "#include <stdio.h>\n#include <x.h>\nint main(){return 0;}\n";
const t = p.parse(src);
console.log(t.rootNode.type);
for (const ch of t.rootNode.namedChildren) console.log(" ", ch.type);
p.delete();
t.delete();
