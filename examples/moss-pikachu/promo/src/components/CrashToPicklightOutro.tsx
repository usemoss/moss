import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { CrashTogetherText, FAVORITE_PRODUCT_CRASH } from "./CrashTogetherText";
import { MossSymbol } from "./MossWordmark";
import { PicklightWordmark } from "./PicklightWordmark";
import { colors } from "../lib/colors";
import { cinematicEase, smoothEase, slamEase } from "../lib/easing";

export const CrashToPicklightOutro: React.FC = () => {
  const frame = useCurrentFrame();

  const morphProgress = interpolate(frame, [35, 58], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  const lockupOpacity = interpolate(frame, [48, 62], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const lockupScale = interpolate(frame, [48, 68], [0.85, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: cinematicEase,
  });

  const lockupBlur = interpolate(frame, [48, 62], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const glowOpacity = interpolate(frame, [55, 72], [0, 0.5], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const petScale = interpolate(frame, [58, 72], [0.3, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const petOpacity = interpolate(frame, [58, 70], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const poweredOpacity = interpolate(frame, [88, 108], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const poweredY = interpolate(frame, [88, 108], [14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 32,
      }}
    >
      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
        {morphProgress < 1 && (
          <div style={{ position: "absolute" }}>
            <CrashTogetherText
              words={FAVORITE_PRODUCT_CRASH}
              fontSize={64}
              hold
              morphProgress={morphProgress}
            />
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 32,
            opacity: lockupOpacity,
            scale: lockupScale,
            filter: lockupBlur > 0.1 ? `blur(${lockupBlur}px)` : undefined,
          }}
        >
          <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div
              style={{
                position: "absolute",
                width: 400,
                height: 400,
                borderRadius: "50%",
                background: "radial-gradient(circle, #FFD60A 0%, transparent 70%)",
                filter: "blur(50px)",
                opacity: glowOpacity,
              }}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <Img
                src={staticFile("pet/capvolt-sticker.png")}
                style={{
                  width: 72,
                  height: 72,
                  imageRendering: "pixelated",
                  opacity: petOpacity,
                  scale: petScale,
                }}
              />
              <PicklightWordmark size={72} variant="large" />
            </div>
          </div>

          {frame >= 88 && (
            <div
              style={{
                opacity: poweredOpacity,
                translate: `0 ${poweredY}px`,
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "14px 36px",
                background: "rgba(255,255,255,0.1)",
                backdropFilter: "blur(20px)",
                borderRadius: 28,
                border: `1px solid ${colors.glassBorder}`,
              }}
            >
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  color: colors.secondaryText,
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  letterSpacing: 1,
                }}
              >
                Powered by
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
          )}
        </div>
      </div>
    </div>
  );
};
