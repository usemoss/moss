import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { slamEase, smoothEase } from "../lib/easing";

type SuperpowerCardProps = {
  title: string;
  subtitle: string;
  index: number;
  enterFrame: number;
  fromX: number;
  fromY: number;
  drift?: number;
};

export const SuperpowerCard: React.FC<SuperpowerCardProps> = ({
  title,
  subtitle,
  index,
  enterFrame,
  fromX,
  fromY,
  drift = 0,
}) => {
  const frame = useCurrentFrame();
  const local = frame - enterFrame;

  const progress = interpolate(local, [0, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  const x = interpolate(progress, [0, 1], [fromX, 0]) + Math.sin((frame + index * 20) / 28) * drift;
  const y = interpolate(progress, [0, 1], [fromY, 0]) + Math.cos((frame + index * 15) / 32) * drift * 0.6;
  const opacity = interpolate(local, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  const scale = interpolate(progress, [0, 1], [0.82, 1]);

  return (
    <div
      style={{
        width: "100%",
        boxSizing: "border-box",
        padding: "28px 26px",
        borderRadius: 16,
        background: "rgba(20,25,22,0.82)",
        border: "1px solid rgba(255,214,10,0.28)",
        boxShadow: "0 20px 50px rgba(0,0,0,0.45), 0 0 24px rgba(255,214,10,0.08)",
        opacity,
        translate: `${x}px ${y}px`,
        scale,
        backdropFilter: "blur(12px)",
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: 2,
          textTransform: "uppercase",
          color: colors.brandYellow,
          marginBottom: 10,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
      >
        {String(index + 1).padStart(2, "0")}
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color: colors.white,
          letterSpacing: -0.8,
          marginBottom: 8,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: 17,
          fontWeight: 500,
          color: colors.secondaryText,
          lineHeight: 1.35,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
      >
        {subtitle}
      </div>
    </div>
  );
};
