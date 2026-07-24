import { interpolate, useCurrentFrame } from "remotion";
import { dropEase, slamEase, snapEase } from "../lib/easing";

type DropTextProps = {
  children: React.ReactNode;
  size?: number;
  color?: string;
  delay?: number;
  weight?: number;
  dropDistance?: number;
  variant?: "drop" | "slam" | "fade";
  align?: "left" | "center" | "right";
  letterSpacing?: number;
};

export const DropText: React.FC<DropTextProps> = ({
  children,
  size = 72,
  color = "#F1F1F1",
  delay = 0,
  weight = 700,
  dropDistance = 140,
  variant = "drop",
  align = "center",
  letterSpacing = -2,
}) => {
  const frame = useCurrentFrame();
  const localFrame = Math.max(0, frame - delay);
  const duration = variant === "slam" ? 22 : 28;

  const easing = variant === "slam" ? slamEase : variant === "drop" ? dropEase : snapEase;

  const y = interpolate(localFrame, [0, duration], [-dropDistance, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });

  const scale = interpolate(
    localFrame,
    [0, duration * 0.7, duration],
    variant === "slam" ? [1.14, 1.02, 1] : [0.94, 1.01, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing,
    },
  );

  const opacity = interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const blur = interpolate(localFrame, [0, 12], [6, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        fontSize: size,
        fontWeight: weight,
        color,
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        lineHeight: 1.08,
        letterSpacing,
        opacity,
        translate: `0 ${y}px`,
        scale,
        textAlign: align,
        filter: blur > 0.1 ? `blur(${blur}px)` : undefined,
      }}
    >
      {children}
    </div>
  );
};
