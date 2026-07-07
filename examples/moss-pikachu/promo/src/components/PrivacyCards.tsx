import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { dropEase, snapEase } from "../lib/easing";

const CARDS = [
  {
    title: "100% local search",
    subtitle: "Queries run locally in memory.",
  },
  {
    title: "100% private by design",
    subtitle: "You choose what folders are indexed.",
  },
];

export const PrivacyCards: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        display: "flex",
        gap: 36,
        justifyContent: "center",
        alignItems: "stretch",
      }}
    >
      {CARDS.map((card, i) => {
        const delay = 20 + i * 28;
        const localFrame = frame - delay;
        const scale = interpolate(localFrame, [0, 22], [0.82, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: snapEase,
        });
        const opacity = interpolate(localFrame, [0, 14], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const y = interpolate(localFrame, [0, 22], [80, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: dropEase,
        });

        return (
          <div
            key={card.title}
            style={{
              width: 420,
              padding: "40px 36px",
              background: "rgba(255,255,255,0.06)",
              border: `1px solid ${colors.glassBorder}`,
              borderRadius: 22,
              opacity,
              scale,
              translate: `0 ${y}px`,
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                background: colors.accentGreen,
                transform: "rotate(45deg)",
                marginBottom: 24,
              }}
            />
            <div
              style={{
                fontSize: 44,
                fontWeight: 700,
                color: colors.white,
                fontFamily: "system-ui, sans-serif",
                lineHeight: 1.15,
                marginBottom: 14,
                letterSpacing: -1,
              }}
            >
              {card.title}
            </div>
            <div
              style={{
                fontSize: 22,
                color: colors.secondaryText,
                fontFamily: "system-ui, sans-serif",
                lineHeight: 1.35,
              }}
            >
              {card.subtitle}
            </div>
          </div>
        );
      })}
    </div>
  );
};
