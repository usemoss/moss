import { interpolate, useCurrentFrame } from "remotion";
import { smoothEase } from "../lib/easing";

export const FadeIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  duration?: number;
}> = ({ children, delay = 0, duration = 25 }) => {
  const frame = useCurrentFrame();
  const localFrame = frame - delay;
  const opacity = interpolate(localFrame, [0, duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  return <div style={{ opacity }}>{children}</div>;
};
