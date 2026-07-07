import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { slamEase, smoothEase } from "../lib/easing";

export type CrashWord = {
  text: string;
  fromX: number;
  fromY: number;
  highlight?: boolean;
};

type CrashTogetherTextProps = {
  words: CrashWord[];
  fadeOutStart?: number;
  fontSize?: number;
  hold?: boolean;
  morphProgress?: number;
};

export const CrashTogetherText: React.FC<CrashTogetherTextProps> = ({
  words,
  fadeOutStart,
  fontSize = 72,
  hold = false,
  morphProgress = 0,
}) => {
  const frame = useCurrentFrame();
  const collisionFrame = 22;

  const groupScale = interpolate(
    frame,
    [collisionFrame, collisionFrame + 6, collisionFrame + 14],
    [1.08, 1, 1 - morphProgress * 0.75],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: slamEase },
  );

  const groupOpacity =
    !hold && fadeOutStart !== undefined && frame >= fadeOutStart
      ? interpolate(frame, [fadeOutStart, fadeOutStart + 10], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        })
      : interpolate(frame, [0, 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        }) * (1 - morphProgress);

  const groupBlur = morphProgress * 12;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: "12px 18px",
        maxWidth: 1000,
        opacity: groupOpacity,
        scale: groupScale,
        filter: groupBlur > 0.1 ? `blur(${groupBlur}px)` : undefined,
      }}
    >
      {words.map((word, i) => {
        const delay = i * 3;
        const localFrame = Math.max(0, frame - delay);
        const progress = interpolate(localFrame, [0, collisionFrame], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        });

        const x = interpolate(progress, [0, 1], [word.fromX, 0]);
        const y = interpolate(progress, [0, 1], [word.fromY, 0]);
        const highlighted = word.highlight ?? false;

        return (
          <span
            key={`${word.text}-${i}`}
            style={{
              fontSize,
              fontWeight: 800,
              color: highlighted ? colors.brandYellow : colors.white,
              textShadow: highlighted ? colors.brandYellowHalo : undefined,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -2,
              translate: `${x}px ${y}px`,
              lineHeight: 1,
            }}
          >
            {word.text}
          </span>
        );
      })}
    </div>
  );
};

export const FAVORITE_PRODUCT_CRASH: CrashWord[] = [
  { text: "your", fromX: -240, fromY: -90 },
  { text: "favorite", fromX: -40, fromY: 100 },
  { text: "product", fromX: 260, fromY: -70, highlight: true },
];
