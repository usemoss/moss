import "./index.css";
import { Composition } from "remotion";
import { MossVscodePromo } from "./compositions/MossVscodePromo";
import { FPS, TOTAL_FRAMES } from "./lib/timing";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="MossVscodePromo"
      component={MossVscodePromo}
      durationInFrames={TOTAL_FRAMES}
      fps={FPS}
      width={1920}
      height={1080}
    />
  </>
);
