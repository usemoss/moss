export const materials = {
  spotlight: {
    background: "rgba(255,255,255,0.14)",
    backdropFilter: "blur(32px)",
    border: "1px solid rgba(255,255,255,0.22)",
    boxShadow: "0 8px 32px rgba(0,0,0,0.35)",
  },
  panel: {
    background: "rgba(255,255,255,0.10)",
    backdropFilter: "blur(28px)",
    border: "1px solid rgba(255,255,255,0.18)",
    boxShadow: "0 16px 48px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08)",
  },
  dock: {
    background: "rgba(255,255,255,0.18)",
    backdropFilter: "blur(24px)",
    border: "1px solid rgba(255,255,255,0.22)",
    boxShadow: "0 4px 24px rgba(0,0,0,0.25)",
  },
  bubble: {
    background: "rgba(255,255,255,0.12)",
    backdropFilter: "blur(24px)",
    border: "1px solid rgba(255,255,255,0.2)",
    boxShadow: "0 20px 56px rgba(0,0,0,0.45)",
  },
} as const;
