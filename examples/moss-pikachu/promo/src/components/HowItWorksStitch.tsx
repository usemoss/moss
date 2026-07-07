import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { dropEase, smoothEase } from "../lib/easing";
import { StepIcon } from "./MacIcons";

const STEPS = [
  { num: "1", label: "Choose folders", icon: "folder" as const },
  { num: "2", label: "Picklight indexes meaning", icon: "sparkle" as const },
  { num: "3", label: "Ask naturally", icon: "bubble" as const },
  { num: "4", label: "Open the right file", icon: "check" as const },
];

export const HowItWorksStitch: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {STEPS.map((step, i) => {
        const delay = i * 32;
        const localFrame = frame - delay;
        const opacity = interpolate(localFrame, [0, 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        });
        const scale = interpolate(localFrame, [0, 22], [0.75, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: dropEase,
        });
        const y = interpolate(localFrame, [0, 22], [60, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: dropEase,
        });
        const lineWidth = interpolate(localFrame, [12, 32], [0, 72], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <div key={step.num} style={{ display: "flex", alignItems: "center" }}>
            <div
              style={{
                width: 220,
                padding: "32px 22px",
                background: "rgba(255,255,255,0.06)",
                border: `1px solid ${colors.glassBorder}`,
                borderRadius: 18,
                textAlign: "center",
                opacity,
                scale,
                translate: `0 ${y}px`,
              }}
            >
              <div style={{ marginBottom: 10, display: "flex", justifyContent: "center" }}>
                <StepIcon variant={step.icon} size={36} />
              </div>
              <div
                style={{
                  fontSize: 16,
                  color: colors.secondaryText,
                  fontFamily: "system-ui, sans-serif",
                  marginBottom: 8,
                  fontWeight: 500,
                }}
              >
                Step {step.num}
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 700,
                  color: colors.white,
                  fontFamily: "system-ui, sans-serif",
                  lineHeight: 1.25,
                }}
              >
                {step.label}
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  width: lineWidth,
                  height: 3,
                  background: colors.accentGreen,
                  opacity: 0.7,
                  borderRadius: 2,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
};
