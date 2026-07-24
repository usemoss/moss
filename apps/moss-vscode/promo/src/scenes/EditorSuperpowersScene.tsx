import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SuperpowerCard } from "../components/SuperpowerCard";
import { colors } from "../lib/colors";
import { smoothEase } from "../lib/easing";
import { SCENES } from "../lib/timing";

const CARDS = [
  {
    title: "Live search",
    subtitle: "Type meaning, not keywords",
    enter: 18,
    fromX: -360,
    fromY: -40,
  },
  {
    title: "Click to jump",
    subtitle: "Land on the exact line",
    enter: 38,
    fromX: 360,
    fromY: -40,
  },
  {
    title: "Stays indexed",
    subtitle: "Reopen. Search instantly.",
    enter: 58,
    fromX: -360,
    fromY: 40,
  },
  {
    title: "Cloud optional",
    subtitle: "Sync when you want",
    enter: 78,
    fromX: 360,
    fromY: 40,
  },
] as const;

export const EditorSuperpowersScene: React.FC = () => {
  const frame = useCurrentFrame();

  const eyebrowOpacity = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const footerOpacity = interpolate(frame, [110, 130], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const silhouetteOpacity = interpolate(frame, [0, 20], [0, 0.14], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <SequoiaBackdrop scrimOpacity={0.52} backdropScale={1.02}>
      <SceneBridge sceneDuration={SCENES.superpowers.duration} exitDuration={15}>
        <AbsoluteFill
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* Centered dim VS Code silhouette behind cards */}
          <div
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              width: 880,
              height: 520,
              translate: "-50% -50%",
              borderRadius: 12,
              background: "rgba(30,30,30,0.9)",
              border: "1px solid rgba(255,255,255,0.08)",
              opacity: silhouetteOpacity,
              boxShadow: "0 40px 100px rgba(0,0,0,0.5)",
              pointerEvents: "none",
            }}
          >
            <div
              style={{
                height: 28,
                background: "#323233",
                borderBottom: "1px solid #474747",
                borderRadius: "12px 12px 0 0",
              }}
            />
            <div style={{ display: "flex", height: "calc(100% - 28px)" }}>
              <div style={{ width: 40, background: "#333" }} />
              <div
                style={{
                  width: 160,
                  background: "#252526",
                  borderRight: "1px solid #474747",
                }}
              />
              <div style={{ flex: 1, background: "#1e1e1e" }} />
            </div>
          </div>

          <div
            style={{
              opacity: eyebrowOpacity,
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: 4,
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.5)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              marginBottom: 40,
              textAlign: "center",
              zIndex: 1,
            }}
          >
            In your editor
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "340px 340px",
              gridTemplateRows: "auto auto",
              gap: 24,
              width: 704,
              justifyContent: "center",
              alignContent: "center",
              zIndex: 1,
            }}
          >
            {CARDS.map((card, i) => (
              <SuperpowerCard
                key={card.title}
                index={i}
                title={card.title}
                subtitle={card.subtitle}
                enterFrame={card.enter}
                fromX={card.fromX}
                fromY={card.fromY}
                drift={0}
              />
            ))}
          </div>

          <div
            style={{
              marginTop: 40,
              opacity: footerOpacity,
              fontSize: 22,
              fontWeight: 600,
              color: colors.secondaryText,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              textAlign: "center",
              zIndex: 1,
            }}
          >
            Built for VS Code & Cursor
          </div>
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
