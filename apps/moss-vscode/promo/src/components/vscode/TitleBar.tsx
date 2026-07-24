import { vscode } from "../../lib/colors";

export const TitleBar: React.FC<{ title?: string }> = ({
  title = "acme-api — Moss Code Search — Visual Studio Code",
}) => (
  <div
    style={{
      height: 35,
      background: vscode.titleBar,
      display: "flex",
      alignItems: "center",
      padding: "0 14px",
      flexShrink: 0,
      borderBottom: `1px solid ${vscode.border}`,
    }}
  >
    <div style={{ display: "flex", gap: 8, width: 70 }}>
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
    </div>
    <div
      style={{
        flex: 1,
        textAlign: "center",
        fontSize: 12,
        color: vscode.foreground,
        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        fontWeight: 400,
        opacity: 0.85,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {title}
    </div>
    <div style={{ width: 70 }} />
  </div>
);
