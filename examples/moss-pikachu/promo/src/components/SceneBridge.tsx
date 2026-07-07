import { interpolate, useCurrentFrame } from "remotion";
import { smoothEase } from "../lib/easing";

type SceneBridgeProps = {
  children: React.ReactNode;
  /** Fade in over first N frames */
  enterDuration?: number;
  /** Fade out over last N frames */
  exitDuration?: number;
  sceneDuration: number;
  blurOnExit?: boolean;
};

export const SceneBridge: React.FC<SceneBridgeProps> = ({
  children,
  enterDuration = 15,
  exitDuration = 15,
  sceneDuration,
  blurOnExit = false,
}) => {
  const frame = useCurrentFrame();

  const enterOpacity = interpolate(frame, [0, enterDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const exitStart = sceneDuration - exitDuration;
  const exitOpacity =
    exitDuration > 0
      ? interpolate(frame, [exitStart, sceneDuration], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        })
      : 1;

  const opacity = Math.min(enterOpacity, exitOpacity);

  const exitBlur = blurOnExit
    ? interpolate(frame, [exitStart, sceneDuration], [0, 8], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const enterScale = interpolate(frame, [0, enterDuration], [1.02, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        opacity,
        scale: enterScale,
        filter: exitBlur > 0.1 ? `blur(${exitBlur}px)` : undefined,
      }}
    >
      {children}
    </div>
  );
};
