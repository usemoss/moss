import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";

export const VfxLayer: React.FC<{
  vignette?: boolean;
  grain?: boolean;
  chromatic?: number;
}> = ({ vignette = true, grain = true, chromatic = 0 }) => {
  const frame = useCurrentFrame();
  const grainOpacity = interpolate(frame % 4, [0, 2, 4], [0.04, 0.06, 0.04]);

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {chromatic > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.05,
            backgroundColor: "rgba(255,0,80,0.1)",
            translate: `${chromatic}px 0`,
          }}
        />
      )}
      {grain && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            opacity: grainOpacity,
            backgroundColor: "rgba(255,255,255,0.02)",
          }}
        />
      )}
      {vignette && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.6) 100%)",
          }}
        />
      )}
    </AbsoluteFill>
  );
};

export const DiagonalWipe: React.FC<{ progress: number }> = ({ progress }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      background: colors.mossCharcoal,
      clipPath: `polygon(0 0, ${progress * 120}% 0, ${progress * 120 - 20}% 100%, 0 100%)`,
    }}
  />
);
