import { AbsoluteFill } from "remotion";
import { CrashToPicklightOutro } from "../components/CrashToPicklightOutro";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";

export const OutroScene: React.FC = () => (
  <SequoiaBackdrop scrimOpacity={0.52} scrimBoost={0.1}>
    <SceneBridge sceneDuration={SCENES.outro.duration} enterDuration={15}>
      <AbsoluteFill>
        <CrashToPicklightOutro />
      </AbsoluteFill>
    </SceneBridge>
  </SequoiaBackdrop>
);
