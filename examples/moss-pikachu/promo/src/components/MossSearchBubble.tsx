import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { dropEase } from "../lib/easing";
import { MacFileIcon } from "./MacIcons";
import { PicklightWordmark } from "./PicklightWordmark";

type MossSearchBubbleProps = {
  query: string;
  showResult?: boolean;
  glow?: boolean;
  selected?: boolean;
  opacity?: number;
};

export const MossSearchBubble: React.FC<MossSearchBubbleProps> = ({
  query,
  showResult = false,
  glow = false,
  selected = false,
  opacity: bubbleOpacity = 1,
}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 18], [0.88, 1], {
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const y = interpolate(frame, [0, 18], [30, 0], {
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const glowOpacity = glow
    ? interpolate(frame, [0, 25], [0, 0.85], { extrapolateRight: "clamp" })
    : 0;

  return (
    <div style={{ position: "relative", scale, translate: `0 ${y}px`, opacity: bubbleOpacity }}>
      {glow && (
        <div
          style={{
            position: "absolute",
            inset: -24,
            borderRadius: 28,
            background: `radial-gradient(circle, ${colors.accentGreen} 0%, transparent 70%)`,
            opacity: glowOpacity,
            filter: "blur(24px)",
          }}
        />
      )}
      <div
        style={{
          width: 400,
          background: colors.glassFill,
          backdropFilter: "blur(24px)",
          borderRadius: 20,
          border: `1px solid ${colors.glassBorder}`,
          boxShadow: "0 20px 56px rgba(0,0,0,0.45)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "16px 20px" }}>
          <div style={{ marginBottom: 10 }}>
            <PicklightWordmark size={18} />
          </div>
          <div
            style={{
              fontSize: 14,
              color: colors.secondaryText,
              marginBottom: 8,
              fontFamily: "system-ui, sans-serif",
            }}
          >
            What are you looking for?
          </div>
          <div
            style={{
              fontSize: 22,
              color: colors.white,
              fontFamily: "system-ui, sans-serif",
              fontWeight: 500,
            }}
          >
            {query}
          </div>
        </div>
        {showResult && (
          <div
            style={{
              borderTop: `1px solid ${colors.glassBorder}`,
              padding: "14px 20px",
              background: selected
                ? "rgba(0, 122, 255, 0.28)"
                : "rgba(26,61,46,0.4)",
              borderLeft: `4px solid ${colors.accentGreen}`,
              borderLeftWidth: selected ? 0 : 4,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <MacFileIcon variant="pdf" size={36} />
            <div>
              <div
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  color: colors.white,
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                lease-2024-final.pdf
              </div>
              <div
                style={{
                  fontSize: 14,
                  color: colors.secondaryText,
                  marginTop: 4,
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                Residential lease agreement between parties…
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export const AvatarStack: React.FC<{ delay?: number }> = ({ delay = 0 }) => {
  const frame = useCurrentFrame();
  const localFrame = frame - delay;
  const scale = interpolate(localFrame, [0, 20], [0.6, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const y = interpolate(localFrame, [0, 20], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const opacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        opacity,
        scale,
        translate: `0 ${y}px`,
      }}
    >
      <Img
        src={staticFile("pet/capvolt-sticker.png")}
        style={{
          width: 88,
          height: 88,
          imageRendering: "pixelated",
        }}
      />
    </div>
  );
};
