import { interpolate, useCurrentFrame } from "remotion";
import { RUNNER_UP_FILE, SEMANTIC_QUERY, WINNING_FILE, WINNING_SNIPPET } from "../lib/demo";
import { colors } from "../lib/colors";
import { dropEase } from "../lib/easing";
import { materials } from "../lib/materials";
import { MacFileIcon } from "./MacIcons";

type CloudBubbleProps = {
  query: string;
  showThinking?: boolean;
  showResults?: boolean;
  glow?: boolean;
  selected?: boolean;
  opacity?: number;
  enterFrame?: number;
};

export const CloudBubble: React.FC<CloudBubbleProps> = ({
  query,
  showThinking = false,
  showResults = false,
  glow = false,
  selected = false,
  opacity: bubbleOpacity = 1,
  enterFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const local = Math.max(0, frame - enterFrame);

  const scale = interpolate(local, [0, 18], [0.88, 1], {
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const y = interpolate(local, [0, 18], [30, 0], {
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const glowOpacity = glow
    ? interpolate(local, [0, 25], [0, 0.85], { extrapolateRight: "clamp" })
    : 0;

  return (
    <div
      style={{
        position: "relative",
        width: 300,
        opacity: bubbleOpacity,
        scale,
        translate: `0 ${y}px`,
      }}
    >
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

      <div style={{ position: "relative" }}>
        <div
          style={{
            background: materials.bubble.background,
            backdropFilter: materials.bubble.backdropFilter,
            borderRadius: 18,
            border: materials.bubble.border,
            boxShadow: materials.bubble.boxShadow,
            overflow: "hidden",
          }}
        >
          <div style={{ padding: "14px 16px" }}>
            <div
              style={{
                fontSize: 13,
                color: colors.secondaryText,
                marginBottom: 6,
                fontFamily: "system-ui, sans-serif",
              }}
            >
              What are you looking for?
            </div>
            <div
              style={{
                fontSize: 17,
                color: colors.white,
                fontFamily: "system-ui, sans-serif",
                fontWeight: 500,
                minHeight: 24,
              }}
            >
              {query}
              {query.length < SEMANTIC_QUERY.length && (
                <span style={{ opacity: frame % 24 < 12 ? 1 : 0 }}>|</span>
              )}
            </div>
          </div>

          {showThinking && (
            <div
              style={{
                padding: "10px 16px",
                borderTop: `1px solid ${colors.glassBorder}`,
                fontSize: 13,
                color: colors.secondaryText,
                fontFamily: "system-ui, sans-serif",
              }}
            >
              Thinking…
            </div>
          )}

          {showResults && (
            <div style={{ borderTop: `1px solid ${colors.glassBorder}` }}>
              <ResultRow
                name={WINNING_FILE}
                snippet={WINNING_SNIPPET}
                highlight={selected || glow}
                primary
              />
              <ResultRow name={RUNNER_UP_FILE} snippet="January redlines and notes" dimmed />
            </div>
          )}
        </div>

        {/* Thought bubble tail dots */}
        <div style={{ position: "absolute", left: 22, bottom: -18, display: "flex", gap: 5 }}>
          {[10, 7, 5].map((size, i) => (
            <div
              key={i}
              style={{
                width: size,
                height: size,
                borderRadius: "50%",
                background: materials.bubble.background,
                border: materials.bubble.border,
                backdropFilter: materials.bubble.backdropFilter,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

const ResultRow: React.FC<{
  name: string;
  snippet: string;
  highlight?: boolean;
  primary?: boolean;
  dimmed?: boolean;
}> = ({ name, snippet, highlight, primary, dimmed }) => (
  <div
    style={{
      display: "flex",
      alignItems: "flex-start",
      gap: 10,
      padding: "10px 14px",
      background: highlight ? "rgba(0, 122, 255, 0.22)" : "transparent",
      borderLeft: primary && highlight ? "3px solid #34C759" : "3px solid transparent",
      opacity: dimmed ? 0.55 : 1,
    }}
  >
    <MacFileIcon variant="pdf" size={28} />
    <div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: colors.white,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {name}
      </div>
      <div
        style={{
          fontSize: 11,
          color: colors.secondaryText,
          fontFamily: "system-ui, sans-serif",
          marginTop: 2,
        }}
      >
        {snippet}
      </div>
    </div>
  </div>
);
