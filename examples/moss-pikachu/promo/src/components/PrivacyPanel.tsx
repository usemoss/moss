import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { smoothEase } from "../lib/easing";
import { materials } from "../lib/materials";

const ROWS = [
  {
    title: "Your folders, your Mac",
    subtitle: "Documents, Desktop, Downloads — indexed where they live.",
    icon: "folder" as const,
  },
  {
    title: "Local in-memory search",
    subtitle: "Queries run on your Mac — no cloud round-trip per search.",
    icon: "lock" as const,
  },
  {
    title: "Powered by Moss",
    subtitle: "Hybrid retrieval — semantic + keyword, sub-10ms lookups.",
    icon: "sparkle" as const,
  },
];

const LockIcon: React.FC<{ size?: number }> = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <rect x="5" y="11" width="14" height="10" rx="2" stroke="rgba(255,255,255,0.85)" strokeWidth="1.8" />
    <path
      d="M8 11V8a4 4 0 018 0v3"
      stroke="rgba(255,255,255,0.85)"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

const FolderIcon: React.FC<{ size?: number }> = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M3 7.5A1.5 1.5 0 014.5 6H9l2 2h8.5A1.5 1.5 0 0121 9.5v9A1.5 1.5 0 0119.5 20h-15A1.5 1.5 0 013 18.5v-11z"
      stroke="rgba(255,255,255,0.85)"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);

const SparkleIcon: React.FC<{ size?: number }> = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
    <path
      d="M12 3l1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4L12 3z"
      stroke="rgba(255,214,10,0.95)"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <path
      d="M19 14l0.7 2.3L22 17l-2.3 0.7L19 20l-0.7-2.3L16 17l2.3-0.7L19 14z"
      stroke="rgba(255,214,10,0.75)"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
  </svg>
);

export const PrivacyPanel: React.FC = () => {
  const frame = useCurrentFrame();
  const panelOpacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  const panelY = interpolate(frame, [0, 14], [16, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div
      style={{
        width: 720,
        background: materials.panel.background,
        backdropFilter: materials.panel.backdropFilter,
        borderRadius: 20,
        border: materials.panel.border,
        boxShadow: materials.panel.boxShadow,
        overflow: "hidden",
        opacity: panelOpacity,
        translate: `0 ${panelY}px`,
      }}
    >
      <div
        style={{
          padding: "22px 32px 18px",
          borderBottom: `1px solid ${colors.glassBorder}`,
        }}
      >
        <div
          style={{
            fontSize: 44,
            fontWeight: 700,
            color: colors.white,
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            letterSpacing: -1.5,
            lineHeight: 1.1,
          }}
        >
          Search by meaning. Files stay on your Mac.
        </div>
      </div>

      {ROWS.map((row, i) => {
        const delay = [30, 50, 70][i];
        const localFrame = frame - delay;
        const rowOpacity = interpolate(localFrame, [0, 14], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        });
        const rowY = interpolate(localFrame, [0, 14], [10, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        });

        return (
          <div key={row.title}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 20,
                padding: "20px 32px",
                opacity: rowOpacity,
                translate: `0 ${rowY}px`,
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 10,
                  background: "rgba(255,255,255,0.08)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {row.icon === "lock" ? (
                  <LockIcon />
                ) : row.icon === "sparkle" ? (
                  <SparkleIcon />
                ) : (
                  <FolderIcon />
                )}
              </div>
              <div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 600,
                    color: colors.white,
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    lineHeight: 1.2,
                  }}
                >
                  {row.title}
                </div>
                <div
                  style={{
                    fontSize: 18,
                    color: colors.secondaryText,
                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                    marginTop: 4,
                    lineHeight: 1.35,
                  }}
                >
                  {row.subtitle}
                </div>
              </div>
            </div>
            {i < ROWS.length - 1 && (
              <div
                style={{
                  height: 1,
                  margin: "0 32px",
                  background: colors.glassBorder,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
