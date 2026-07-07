import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { MossSymbol } from "./MossWordmark";
import { PicklightWordmark } from "./PicklightWordmark";
import { colors } from "../lib/colors";
import { smoothEase } from "../lib/easing";

type BrandLockupProps = {
  fadeInStart?: number;
  fadeOutStart?: number;
  petSize?: number;
};

export const BrandLockup: React.FC<BrandLockupProps> = ({
  fadeInStart = 0,
  fadeOutStart,
  petSize = 56,
}) => {
  const frame = useCurrentFrame();
  const localIn = Math.max(0, frame - fadeInStart);

  const fadeIn = interpolate(localIn, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  const riseIn = interpolate(localIn, [0, 18], [12, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const fadeOut =
    fadeOutStart !== undefined && frame >= fadeOutStart
      ? interpolate(frame, [fadeOutStart, fadeOutStart + 20], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;

  const riseOut =
    fadeOutStart !== undefined && frame >= fadeOutStart
      ? interpolate(frame, [fadeOutStart, fadeOutStart + 20], [0, -20], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 24,
        opacity: fadeIn * fadeOut,
        translate: `0 ${riseIn + riseOut}px`,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <PicklightWordmark size={72} variant="large" />
        <Img
          src={staticFile("pet/capvolt-sticker.png")}
          style={{
            width: petSize,
            height: petSize,
            imageRendering: "pixelated",
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "14px 32px",
          background: "rgba(255,255,255,0.1)",
          backdropFilter: "blur(20px)",
          borderRadius: 28,
          border: `1px solid ${colors.glassBorder}`,
        }}
      >
        <span
          style={{
            fontSize: 22,
            fontWeight: 500,
            color: colors.secondaryText,
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            letterSpacing: 2,
          }}
        >
          by
        </span>
        <MossSymbol size={40} opacity={0.95} />
        <span
          style={{
            fontSize: 26,
            fontWeight: 600,
            color: colors.white,
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            letterSpacing: 1.5,
          }}
        >
          Moss
        </span>
      </div>
    </div>
  );
};
