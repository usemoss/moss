import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { MossValueRail } from "../components/MossValueRail";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";

export const MossDifferentiatorsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const backdropScale = interpolate(frame, [0, SCENES.mossDifferentiators.duration], [1, 1.03], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <SequoiaBackdrop scrimOpacity={0.5} backdropScale={backdropScale}>
      <SceneBridge sceneDuration={SCENES.mossDifferentiators.duration} exitDuration={15}>
        <AbsoluteFill
          style={{
            justifyContent: "flex-start",
            alignItems: "center",
            paddingTop: 72,
            paddingLeft: 48,
            paddingRight: 48,
          }}
        >
          <MossValueRail />
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
