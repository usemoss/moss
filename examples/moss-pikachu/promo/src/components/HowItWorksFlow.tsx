import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { smoothEase } from "../lib/easing";
import { StepIcon } from "./MacIcons";

const STEPS = [
  { num: "1", label: "Choose folders", icon: "folder" as const },
  { num: "2", label: "Picklight indexes meaning", icon: "sparkle" as const },
  { num: "3", label: "Ask naturally", icon: "bubble" as const },
  { num: "4", label: "Open the right file", icon: "check" as const },
];

export const HowItWorksFlow: React.FC = () => {
  const frame = useCurrentFrame();
  const lineWidth = interpolate(frame, [8, 48], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 56 }}>
      <div
        style={{
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 4,
          color: colors.secondaryText,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          textTransform: "uppercase",
          opacity: interpolate(frame, [0, 12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        How it works
      </div>

      <div style={{ position: "relative", display: "flex", alignItems: "flex-start", gap: 0 }}>
        <div
          style={{
            position: "absolute",
            top: 34,
            left: 60,
            right: 60,
            height: 2,
            background: "rgba(255,255,255,0.12)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 34,
            left: 60,
            width: `${lineWidth}%`,
            maxWidth: "calc(100% - 120px)",
            height: 2,
            background: colors.accentGreen,
            opacity: 0.8,
            borderRadius: 1,
          }}
        />

        {STEPS.map((step, i) => {
          const delay = 12 + i * 14;
          const localFrame = frame - delay;
          const opacity = interpolate(localFrame, [0, 12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: smoothEase,
          });
          const scale = interpolate(localFrame, [0, 12], [0.95, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: smoothEase,
          });

          return (
            <div
              key={step.num}
              style={{
                width: 240,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                opacity,
                scale,
              }}
            >
              <div
                style={{
                  width: 68,
                  height: 68,
                  borderRadius: "50%",
                  background: "rgba(255,255,255,0.1)",
                  border: `1px solid ${colors.glassBorder}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 16,
                  position: "relative",
                  zIndex: 1,
                }}
              >
                <StepIcon variant={step.icon} size={34} />
              </div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: colors.secondaryText,
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  marginBottom: 8,
                }}
              >
                {step.num}
              </div>
              <div
                style={{
                  fontSize: 26,
                  fontWeight: 600,
                  color: colors.white,
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  textAlign: "center",
                  lineHeight: 1.25,
                  padding: "0 8px",
                }}
              >
                {step.label}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
