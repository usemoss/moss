import { vscode } from "../../lib/colors";

export type MossStatus = "idle" | "indexing" | "ready" | "error";

type StatusBarProps = {
  mossStatus?: MossStatus;
  mossLabel?: string;
  branch?: string;
};

export const StatusBar: React.FC<StatusBarProps> = ({
  mossStatus = "idle",
  mossLabel,
  branch = "main",
}) => {
  const mossText =
    mossLabel ??
    (mossStatus === "indexing"
      ? "Moss: indexing…"
      : mossStatus === "ready"
        ? "Moss: ready"
        : mossStatus === "error"
          ? "Moss: error"
          : "Moss");

  return (
    <div
      style={{
        height: 22,
        background: vscode.statusBar,
        display: "flex",
        alignItems: "center",
        padding: "0 10px",
        gap: 14,
        flexShrink: 0,
        fontSize: 12,
        color: "#ffffff",
        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm0 1.5a6.5 6.5 0 110 13 6.5 6.5 0 010-13z" opacity="0" />
          <path d="M5 3.5v9l7-4.5-7-4.5z" />
        </svg>
        {branch}
      </span>
      <span style={{ opacity: 0.9 }}>0 ⚠  0 ✕</span>
      <div style={{ flex: 1 }} />
      <span
        style={{
          background:
            mossStatus === "ready"
              ? "rgba(255,255,255,0.18)"
              : mossStatus === "indexing"
                ? "rgba(255,214,10,0.25)"
                : "rgba(255,255,255,0.12)",
          padding: "1px 8px",
          borderRadius: 3,
          fontWeight: 500,
        }}
      >
        {mossText}
      </span>
      <span>TypeScript</span>
      <span>UTF-8</span>
      <span>LF</span>
    </div>
  );
};
