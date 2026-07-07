import { interpolate, useCurrentFrame } from "remotion";
import { MossSymbol, MossWordmark } from "./MossWordmark";
import { colors } from "../lib/colors";
import { cinematicEase, smoothEase } from "../lib/easing";

export const MossBrandedOutro: React.FC = () => {
  const frame = useCurrentFrame();

  const glowOpacity = interpolate(frame, [0, 24], [0, 0.45], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const lockupOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const lockupScale = interpolate(frame, [0, 28], [0.88, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: cinematicEase,
  });

  const taglineOpacity = interpolate(frame, [28, 44], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const taglineY = interpolate(frame, [28, 44], [12, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const ctaOpacity = interpolate(frame, [70, 88], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const ctaY = interpolate(frame, [70, 88], [10, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const picklightOpacity = interpolate(frame, [100, 118], [0, 1], {
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
      <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div
          style={{
            position: "absolute",
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(255,214,10,0.35) 0%, transparent 70%)",
            filter: "blur(60px)",
            opacity: glowOpacity,
          }}
        />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 24,
            opacity: lockupOpacity,
            scale: lockupScale,
          }}
        >
          <MossSymbol size={88} opacity={1} />
          <MossWordmark width={380} />
        </div>
      </div>

      <div
        style={{
          opacity: taglineOpacity,
          translate: `0 ${taglineY}px`,
          fontSize: 30,
          fontWeight: 600,
          color: colors.white,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          letterSpacing: -0.8,
          textAlign: "center",
          maxWidth: 720,
          lineHeight: 1.25,
        }}
      >
        The retrieval layer for production AI.
      </div>

      {frame >= 70 && (
        <div
          style={{
            opacity: ctaOpacity,
            translate: `0 ${ctaY}px`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              fontSize: 36,
              fontWeight: 700,
              color: colors.brandYellow,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              textShadow: colors.brandYellowHalo,
            }}
          >
            moss<span style={{ textDecoration: "underline" }}>.dev</span>
          </div>
          <div
            style={{
              fontSize: 18,
              fontWeight: 500,
              color: colors.secondaryText,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: 0.2,
            }}
          >
            Connect your data once. Moss keeps indexes fresh.
          </div>
        </div>
      )}

      {frame >= 100 && (
        <div
          style={{
            opacity: picklightOpacity,
            fontSize: 16,
            fontWeight: 500,
            color: "rgba(255,255,255,0.4)",
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            letterSpacing: 0.3,
          }}
        >
          Picklight for Mac — built on Moss
        </div>
      )}
    </div>
  );
};
