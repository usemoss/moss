import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { CloudBubble } from "../components/CloudBubble";
import { HotkeyBadge } from "../components/HotkeyBadge";
import { IndexingToast } from "../components/IndexingToast";
import { MacScreen } from "../components/MacChrome";
import { PdfPreviewWindow } from "../components/PdfPreviewWindow";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SEMANTIC_QUERY } from "../lib/demo";
import { smoothEase } from "../lib/easing";
import { SCENES } from "../lib/timing";
import { type } from "../lib/typography";
import { getTypedLength } from "../lib/typing";

export const ProductRevealScene: React.FC = () => {
  const frame = useCurrentFrame();

  const eyebrowOpacity = interpolate(frame, [0, 12, 28, 36], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const hotkeyOpacity = interpolate(frame, [0, 8, 22, 30], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const typedLength = getTypedLength(frame, 55, SEMANTIC_QUERY);
  const query = frame < 55 ? "" : SEMANTIC_QUERY.slice(0, typedLength);
  const showBubble = frame >= 28;
  const showThinking = frame >= 85 && frame < 100;
  const showResult = frame >= 100;
  const glow = frame > 115;
  const selected = frame >= 118 && frame < 140;
  const showPdf = frame >= 140;

  const bubbleOpacity = showPdf
    ? interpolate(frame, [140, 152], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smoothEase,
      })
    : 1;

  const exitScale = interpolate(frame, [210, 225], [1, 0.96], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <SequoiaBackdrop scrimOpacity={0.4}>
      <SceneBridge sceneDuration={SCENES.productReveal.duration} exitDuration={15}>
        <AbsoluteFill
          style={{
            justifyContent: "flex-start",
            alignItems: "center",
            paddingTop: 80,
            opacity: eyebrowOpacity,
          }}
        >
          <div
            style={{
              fontSize: type.subhead,
              fontWeight: 600,
              color: "rgba(255,255,255,0.75)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -0.5,
            }}
          >
            Search by meaning.
          </div>
        </AbsoluteFill>

        <MacScreen showPet petAttentive={frame >= 25 && frame < 140}>
          <IndexingToast startFrame={0} />

          {frame < 30 && (
            <AbsoluteFill
              style={{
                justifyContent: "flex-start",
                alignItems: "flex-end",
                padding: "36px 180px 0 0",
                opacity: hotkeyOpacity,
              }}
            >
              <HotkeyBadge pulse={frame < 25} />
            </AbsoluteFill>
          )}

          {showBubble && !showPdf && (
            <AbsoluteFill
              style={{
                justifyContent: "flex-end",
                alignItems: "flex-start",
                padding: "80px 80px 120px 120px",
              }}
            >
              <CloudBubble
                query={query}
                showThinking={showThinking}
                showResults={showResult}
                glow={glow}
                selected={selected}
                opacity={bubbleOpacity}
                enterFrame={28}
              />
            </AbsoluteFill>
          )}

          {showPdf && (
            <AbsoluteFill style={{ scale: exitScale }}>
              <PdfPreviewWindow enterFrame={140} />
            </AbsoluteFill>
          )}
        </MacScreen>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
