import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { DropText } from "../components/DropText";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";
import { type } from "../lib/typography";

export const HeroScene: React.FC = () => {
  const frame = useCurrentFrame();

  const headlineOpacity = interpolate(frame, [0, 14, 105, 120], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <SequoiaBackdrop scrimOpacity={0.42}>
      <SceneBridge sceneDuration={SCENES.hero.duration} exitDuration={12}>
        <AbsoluteFill
          style={{
            justifyContent: "center",
            alignItems: "center",
            flexDirection: "column",
            gap: 14,
            opacity: headlineOpacity,
          }}
        >
          <DropText size={type.display} delay={0} variant="slam" dropDistance={140}>
            You know the code.
          </DropText>
          <DropText
            size={type.headline}
            color="rgba(255,255,255,0.55)"
            delay={12}
            variant="drop"
            dropDistance={120}
            weight={600}
          >
            Just not where it lives.
          </DropText>
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
