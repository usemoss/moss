import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { slamEase, smoothEase } from "../lib/easing";

type CrashTogetherLogosProps = {
  collisionFrame?: number;
  morphProgress?: number;
};

export const CrashTogetherLogos: React.FC<CrashTogetherLogosProps> = ({
  collisionFrame = 28,
  morphProgress = 0,
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame, [0, collisionFrame], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const leftX = interpolate(progress, [0, 1], [-380, -58]);
  const rightX = interpolate(progress, [0, 1], [380, 58]);

  const impactScale = interpolate(
    frame,
    [collisionFrame, collisionFrame + 5, collisionFrame + 14],
    [1.12, 0.96, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: slamEase },
  );

  const groupOpacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  }) * (1 - morphProgress);

  const groupScale = interpolate(morphProgress, [0, 1], [impactScale, 0.35], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const blur = morphProgress * 14;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        width: 320,
        height: 140,
        opacity: groupOpacity,
        scale: groupScale,
        filter: blur > 0.1 ? `blur(${blur}px)` : undefined,
      }}
    >
      <Img
        src={staticFile("branding/vscode/icon.png")}
        style={{
          width: 110,
          height: 110,
          position: "absolute",
          translate: `${leftX}px 0`,
          filter: "drop-shadow(0 12px 28px rgba(0,0,0,0.45))",
        }}
      />
      <Img
        src={staticFile("branding/moss/avatar-core.png")}
        style={{
          width: 110,
          height: 110,
          borderRadius: 22,
          position: "absolute",
          translate: `${rightX}px 0`,
          filter: "drop-shadow(0 12px 28px rgba(0,0,0,0.45))",
        }}
      />
    </div>
  );
};
