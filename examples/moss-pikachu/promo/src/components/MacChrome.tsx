import { AbsoluteFill, Img, staticFile } from "remotion";
import { MenuBarPet } from "./MenuBarPet";
import { materials } from "../lib/materials";

const AppleLogo: React.FC = () => (
  <svg width="14" height="17" viewBox="0 0 814 1000" fill="rgba(255,255,255,0.88)">
    <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-157.5 123.1s-87.3-39.5-167.2-39.5c-76.5 0-103.7 40.8-165.9 40.8s-105.6-57-155.5-127C46.7 790.7 0 663 0 541.8c0-194.4 126.4-297.5 250.8-297.5 66.1 0 121.2 43.4 162.7 43.4 38.5 0 98.5-46 176.5-46 28.2 0 129.9 2.6 197.1 99.2zm-234-181.5c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-.6-14.3-1.9-20.1-50.6 1.9-110.8 33.7-147.1 75.8-28.2 32.4-54.4 83.6-54.4 135.5 0 7.8 1.3 15.6 1.9 18.1 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 134.8-71.3z" />
  </svg>
);

const MENU_ITEMS = ["File", "Edit", "View", "Go", "Window", "Help"];

const DOCK_APPS = [
  "finder",
  "safari",
  "mail",
  "messages",
  "calendar",
  "finder",
  "safari",
  "calendar",
] as const;

const DockIcon: React.FC<{ type: (typeof DOCK_APPS)[number]; running?: boolean }> = ({
  type,
  running,
}) => (
  <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center" }}>
    <Img
      src={staticFile(`macbook/dock/${type}.png`)}
      style={{
        width: 56,
        height: 56,
        borderRadius: 12,
        flexShrink: 0,
        boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
      }}
    />
    {running && (
      <div
        style={{
          width: 4,
          height: 4,
          borderRadius: "50%",
          background: "rgba(255,255,255,0.85)",
          marginTop: 4,
        }}
      />
    )}
  </div>
);

type MacChromeProps = {
  showPet?: boolean;
  petAttentive?: boolean;
};

/** Menu bar + dock overlay — wallpaper comes from SequoiaBackdrop parent */
export const MacChrome: React.FC<MacChromeProps> = ({
  showPet = false,
  petAttentive = false,
}) => (
  <AbsoluteFill style={{ pointerEvents: "none" }}>
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 28,
        background: "rgba(0,0,0,0.22)",
        backdropFilter: "blur(20px)",
        display: "flex",
        alignItems: "center",
        padding: "0 12px 0 14px",
        gap: 14,
        zIndex: 10,
        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      }}
    >
      <AppleLogo />
      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.92)", fontWeight: 600 }}>Finder</div>
      {MENU_ITEMS.map((item) => (
        <div key={item} style={{ fontSize: 13, color: "rgba(255,255,255,0.72)", fontWeight: 400 }}>
          {item}
        </div>
      ))}
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        {showPet && <MenuBarPet attentive={petAttentive} />}
        <svg width="16" height="12" viewBox="0 0 16 12" fill="rgba(255,255,255,0.85)">
          <rect x="0" y="8" width="3" height="4" rx="0.5" />
          <rect x="4.5" y="5" width="3" height="7" rx="0.5" />
          <rect x="9" y="2" width="3" height="10" rx="0.5" />
          <rect x="13" y="0" width="3" height="12" rx="0.5" />
        </svg>
        <svg width="22" height="11" viewBox="0 0 22 11" fill="none">
          <rect x="0.5" y="0.5" width="18" height="10" rx="2" stroke="rgba(255,255,255,0.85)" strokeWidth="1" />
          <rect x="2" y="2" width="13" height="7" rx="1" fill="rgba(255,255,255,0.85)" />
          <rect x="19" y="3.5" width="2" height="4" rx="0.5" fill="rgba(255,255,255,0.6)" />
        </svg>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.88)", fontWeight: 500, whiteSpace: "nowrap" }}>
          Fri Jul 3  5:19 PM
        </div>
      </div>
    </div>
    <div
      style={{
        position: "absolute",
        bottom: 8,
        left: "50%",
        translate: "-50% 0",
        display: "flex",
        gap: 10,
        padding: "8px 14px",
        borderRadius: 22,
        background: materials.dock.background,
        backdropFilter: materials.dock.backdropFilter,
        border: materials.dock.border,
        boxShadow: materials.dock.boxShadow,
      }}
    >
      {DOCK_APPS.map((type, i) => (
        <DockIcon key={`${type}-${i}`} type={type} running={i === 0} />
      ))}
    </div>
  </AbsoluteFill>
);

/** Full-screen macOS chrome layer with content between menu bar and dock */
export const MacScreen: React.FC<{
  children?: React.ReactNode;
  showPet?: boolean;
  petAttentive?: boolean;
}> = ({ children, showPet = false, petAttentive = false }) => (
  <AbsoluteFill>
    {children}
    <MacChrome showPet={showPet} petAttentive={petAttentive} />
  </AbsoluteFill>
);
