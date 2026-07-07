import "./index.css";
import { Composition } from "remotion";
import { PicklightPromo } from "./compositions/PicklightPromo";
import { FPS, TOTAL_FRAMES } from "./lib/timing";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="PicklightPromo"
      component={PicklightPromo}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
