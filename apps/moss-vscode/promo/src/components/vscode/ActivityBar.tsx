import { Img, staticFile } from "remotion";
import { vscode } from "../../lib/colors";

export type ActivityView = "explorer" | "search" | "git" | "run" | "extensions" | "moss";

type ActivityBarProps = {
  active: ActivityView;
  mossPulse?: boolean;
};

const IconWrap: React.FC<{
  active?: boolean;
  children: React.ReactNode;
  pulse?: boolean;
}> = ({ active, children, pulse }) => (
  <div
    style={{
      width: 48,
      height: 48,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      position: "relative",
      opacity: active ? 1 : 0.55,
      background: active ? "rgba(255,255,255,0.04)" : "transparent",
      scale: pulse ? 1.08 : 1,
    }}
  >
    {active && (
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 10,
          bottom: 10,
          width: 2,
          background: "#ffffff",
          borderRadius: 1,
        }}
      />
    )}
    {children}
  </div>
);

const ExplorerIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <path
      d="M4 6.5A1.5 1.5 0 015.5 5H10l2 2h6.5A1.5 1.5 0 0120 8.5v9A1.5 1.5 0 0118.5 19h-13A1.5 1.5 0 014 17.5v-11z"
      stroke="#cccccc"
      strokeWidth="1.5"
    />
  </svg>
);

const SearchIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <circle cx="10.5" cy="10.5" r="5.5" stroke="#cccccc" strokeWidth="1.6" />
    <path d="M15 15l4.5 4.5" stroke="#cccccc" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

const GitIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <circle cx="6" cy="6" r="2" stroke="#cccccc" strokeWidth="1.5" />
    <circle cx="18" cy="12" r="2" stroke="#cccccc" strokeWidth="1.5" />
    <circle cx="6" cy="18" r="2" stroke="#cccccc" strokeWidth="1.5" />
    <path d="M6 8v8M6 12h10" stroke="#cccccc" strokeWidth="1.5" />
  </svg>
);

const RunIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <path d="M8 5.5v13l11-6.5L8 5.5z" fill="#cccccc" />
  </svg>
);

const ExtIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    <rect x="4" y="4" width="7" height="7" rx="1" stroke="#cccccc" strokeWidth="1.5" />
    <rect x="13" y="4" width="7" height="7" rx="1" stroke="#cccccc" strokeWidth="1.5" />
    <rect x="4" y="13" width="7" height="7" rx="1" stroke="#cccccc" strokeWidth="1.5" />
    <rect x="13" y="13" width="7" height="7" rx="1" stroke="#cccccc" strokeWidth="1.5" />
  </svg>
);

export const ActivityBar: React.FC<ActivityBarProps> = ({ active, mossPulse }) => (
  <div
    style={{
      width: 48,
      background: vscode.activityBar,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: 4,
      flexShrink: 0,
      borderRight: `1px solid ${vscode.border}`,
    }}
  >
    <IconWrap active={active === "explorer"}>
      <ExplorerIcon />
    </IconWrap>
    <IconWrap active={active === "search"}>
      <SearchIcon />
    </IconWrap>
    <IconWrap active={active === "git"}>
      <GitIcon />
    </IconWrap>
    <IconWrap active={active === "run"}>
      <RunIcon />
    </IconWrap>
    <IconWrap active={active === "extensions"}>
      <ExtIcon />
    </IconWrap>
    <div style={{ flex: 1 }} />
    <IconWrap active={active === "moss"} pulse={mossPulse}>
      <Img
        src={staticFile("branding/moss/icon.svg")}
        style={{ width: 24, height: 24, opacity: active === "moss" ? 1 : 0.7 }}
      />
    </IconWrap>
  </div>
);
