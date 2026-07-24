import { AbsoluteFill } from "remotion";
import { CrashToMossOutro } from "../components/CrashToMossOutro";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";

export const OutroScene: React.FC = () => (
  <SequoiaBackdrop scrimOpacity={0.54} scrimBoost={0.1}>
    <SceneBridge sceneDuration={SCENES.outro.duration} enterDuration={12}>
      <AbsoluteFill>
        <CrashToMossOutro />
      </AbsoluteFill>
    </SceneBridge>
  </SequoiaBackdrop>
);
