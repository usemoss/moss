import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { CrashTogetherLogos } from "./CrashTogetherLogos";
import { MossWordmark } from "./MossWordmark";
import { colors } from "../lib/colors";
import { cinematicEase, slamEase, smoothEase } from "../lib/easing";

export const CrashToMossOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const collisionFrame = 28;

  const morphProgress = interpolate(frame, [36, 58], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  const lockupOpacity = interpolate(frame, [48, 66], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const lockupScale = interpolate(frame, [48, 72], [0.86, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: cinematicEase,
  });

  const lockupBlur = interpolate(frame, [48, 66], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const subOpacity = interpolate(frame, [78, 98], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const ctaOpacity = interpolate(frame, [100, 120], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const poweredOpacity = interpolate(frame, [140, 165], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const poweredY = interpolate(frame, [140, 165], [16, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        flexDirection: "column",
        gap: 28,
      }}
    >
      <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", minHeight: 160 }}>
        {morphProgress < 1 && (
          <div style={{ position: "absolute" }}>
            <CrashTogetherLogos collisionFrame={collisionFrame} morphProgress={morphProgress} />
          </div>
        )}

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 18,
            opacity: lockupOpacity,
            scale: lockupScale,
            filter: lockupBlur > 0.1 ? `blur(${lockupBlur}px)` : undefined,
          }}
        >
          <div
            style={{
              fontSize: 64,
              fontWeight: 800,
              color: colors.white,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -2.2,
              textAlign: "center",
              lineHeight: 1.05,
            }}
          >
            VS Code{" "}
            <span style={{ color: colors.brandYellow, textShadow: colors.brandYellowHalo }}>
              Finder
            </span>
          </div>
          <MossWordmark width={260} />
        </div>
      </div>

      <div
        style={{
          opacity: subOpacity,
          fontSize: 28,
          fontWeight: 600,
          color: "rgba(255,255,255,0.78)",
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          letterSpacing: -0.5,
        }}
      >
        Moss Code Search
      </div>

      <div
        style={{
          opacity: ctaOpacity,
          fontSize: 20,
          fontWeight: 500,
          color: "rgba(255,255,255,0.55)",
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
      >
        Available on moss.dev
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          opacity: poweredOpacity,
          translate: `0 ${poweredY}px`,
          marginTop: 8,
        }}
      >
        <Img
          src={staticFile("branding/vscode/icon.png")}
          style={{ width: 28, height: 28 }}
        />
        <span
          style={{
            fontSize: 16,
            color: "rgba(255,255,255,0.45)",
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          }}
        >
          ×
        </span>
        <Img
          src={staticFile("branding/moss/avatar-core.png")}
          style={{ width: 28, height: 28, borderRadius: 6 }}
        />
        <span
          style={{
            marginLeft: 6,
            fontSize: 18,
            fontWeight: 600,
            color: "rgba(255,255,255,0.65)",
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          }}
        >
          Powered by Moss
        </span>
      </div>
    </AbsoluteFill>
  );
};
