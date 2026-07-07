import { AbsoluteFill } from "remotion";
import { MossPlatformRail } from "../components/MossPlatformRail";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";

export const MossPlatformScene: React.FC = () => (
  <SequoiaBackdrop scrimOpacity={0.46}>
    <SceneBridge sceneDuration={SCENES.mossPlatform.duration} exitDuration={12}>
      <AbsoluteFill
        style={{
          justifyContent: "flex-start",
          alignItems: "center",
          paddingTop: 72,
          paddingLeft: 48,
          paddingRight: 48,
        }}
      >
        <MossPlatformRail />
      </AbsoluteFill>
    </SceneBridge>
  </SequoiaBackdrop>
);
