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
              "radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.68) 100%)",
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

/** Brief full-frame impact flash — yellow or white */
export const ImpactFlash: React.FC<{
  startFrame: number;
  color?: "yellow" | "white" | "red";
  peak?: number;
  duration?: number;
}> = ({ startFrame, color = "yellow", peak = 0.45, duration = 12 }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  if (local < 0 || local > duration) return null;

  const opacity = interpolate(local, [0, 2, duration], [0, peak, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const bg =
    color === "white"
      ? `rgba(255,255,255,${opacity})`
      : color === "red"
        ? `rgba(255,80,80,${opacity})`
        : `rgba(255,214,10,${opacity})`;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: bg,
        mixBlendMode: color === "red" ? "screen" : "screen",
        pointerEvents: "none",
      }}
    />
  );
};
