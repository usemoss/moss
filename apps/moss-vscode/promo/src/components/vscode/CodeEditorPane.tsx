import { vscode } from "../../lib/colors";

type CodeEditorPaneProps = {
  lines: string[];
  highlightLine?: number | null;
  startLineNumber?: number;
  language?: string;
};

const tokenize = (line: string): React.ReactNode[] => {
  if (line.trimStart().startsWith("//") || line.trimStart().startsWith("*") || line.trimStart().startsWith("/**")) {
    return [<span key="c" style={{ color: vscode.comment }}>{line}</span>];
  }
  if (line.trimStart().startsWith("#")) {
    return [<span key="c" style={{ color: vscode.comment }}>{line}</span>];
  }

  const parts: React.ReactNode[] = [];
  const re =
    /(\b(?:import|export|from|async|function|const|let|var|return|if|while|try|catch|throw|new|type|Promise|await)\b)|("(?:\\.|[^"])*"|'(?:\\.|[^'])*')|(\b\d+\b)|(\b[A-Z][A-Za-z0-9_]*\b)|(\b[a-zA-Z_][a-zA-Z0-9_]*(?=\())|(\/\/.*$)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) {
      parts.push(<span key={`t${i++}`}>{line.slice(last, m.index)}</span>);
    }
    if (m[1]) {
      parts.push(<span key={`k${i++}`} style={{ color: vscode.keyword }}>{m[1]}</span>);
    } else if (m[2]) {
      parts.push(<span key={`s${i++}`} style={{ color: vscode.string }}>{m[2]}</span>);
    } else if (m[3]) {
      parts.push(<span key={`n${i++}`} style={{ color: vscode.number }}>{m[3]}</span>);
    } else if (m[4]) {
      parts.push(<span key={`y${i++}`} style={{ color: vscode.type }}>{m[4]}</span>);
    } else if (m[5]) {
      parts.push(<span key={`f${i++}`} style={{ color: vscode.function }}>{m[5]}</span>);
    } else if (m[6]) {
      parts.push(<span key={`c${i++}`} style={{ color: vscode.comment }}>{m[6]}</span>);
    }
    last = m.index + m[0].length;
  }
  if (last < line.length) {
    parts.push(<span key={`t${i++}`}>{line.slice(last)}</span>);
  }
  return parts.length ? parts : [line || " "];
};

export const CodeEditorPane: React.FC<CodeEditorPaneProps> = ({
  lines,
  highlightLine = null,
  startLineNumber = 1,
}) => (
  <div
    style={{
      flex: 1,
      background: vscode.editor,
      overflow: "hidden",
      fontFamily: '"SF Mono", Menlo, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: "20px",
      color: vscode.foreground,
      display: "flex",
      minHeight: 0,
    }}
  >
    <div
      style={{
        width: 48,
        flexShrink: 0,
        textAlign: "right",
        padding: "8px 10px 8px 0",
        color: vscode.lineNumber,
        userSelect: "none",
        borderRight: `1px solid ${vscode.border}`,
      }}
    >
      {lines.map((_, i) => (
        <div
          key={i}
          style={{
            height: 20,
            background:
              highlightLine === i ? "rgba(38,79,120,0.35)" : "transparent",
          }}
        >
          {startLineNumber + i}
        </div>
      ))}
    </div>
    <div style={{ flex: 1, padding: "8px 0", overflow: "hidden" }}>
      {lines.map((line, i) => (
        <div
          key={i}
          style={{
            height: 20,
            padding: "0 12px",
            whiteSpace: "pre",
            background: highlightLine === i ? vscode.selection : "transparent",
            boxShadow:
              highlightLine === i
                ? "inset 3px 0 0 #007acc"
                : undefined,
          }}
        >
          {tokenize(line)}
        </div>
      ))}
    </div>
  </div>
);
