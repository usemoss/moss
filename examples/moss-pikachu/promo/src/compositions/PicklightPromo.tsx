import { Audio } from "@remotion/media";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { VfxLayer } from "../components/VfxLayer";
import { getMusicSectionVolume } from "../lib/music";
import { SEMANTIC_QUERY } from "../lib/demo";
import {
  CLICK_DUCK_FRAMES,
  CLICK_SFX,
  CLICK_SFX_DURATION,
  CLICK_SFX_PEAK_VOLUME,
  DROP_SFX,
  DROP_SFX_DURATION,
  DROP_SLAM_PEAK_VOLUME,
  DROP_SOFT_PEAK_VOLUME,
  getTypingTickFrames,
  SLAM_DUCK_FRAMES,
  TRANSITION_SFX_DURATION,
  TRANSITION_SFX_FRAMES,
  TRANSITION_SFX_PEAK_VOLUME,
  UI_TICK_DURATION,
  UI_TICK_PEAK_VOLUME,
  type DropVariant,
} from "../lib/sfx";
import { SCENES, TOTAL_FRAMES } from "../lib/timing";
import { MacBookHeroScene } from "../scenes/MacBookHeroScene";
import { MossDifferentiatorsScene } from "../scenes/MossDifferentiatorsScene";
import { MossPlatformScene } from "../scenes/MossPlatformScene";
import { OutroScene } from "../scenes/OutroScene";
import { ProductRevealScene } from "../scenes/ProductRevealScene";
import { SpotlightFailureScene } from "../scenes/SpotlightFailureScene";

const SPOTLIGHT_DUCK = SCENES.spotlight.from + 23;
const PRODUCT_DUCK = SCENES.productReveal.from + 55;

const spotlightTicks = getTypingTickFrames(SCENES.spotlight.from, 15, SEMANTIC_QUERY);
const productTicks = getTypingTickFrames(SCENES.productReveal.from, 55, SEMANTIC_QUERY);

const MusicTrack: React.FC = () => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, 45], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [TOTAL_FRAMES - 60, TOTAL_FRAMES],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const duck = (center: number, half: number, floor: number) =>
    interpolate(
      frame,
      [center - half, center, center + half],
      [1, floor, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );

  const typingDuck = Math.min(
    duck(SPOTLIGHT_DUCK, 20, 0.5),
    duck(PRODUCT_DUCK, 20, 0.5),
  );

  const slamDuck = SLAM_DUCK_FRAMES.reduce(
    (min, center) => Math.min(min, duck(center, 6, 0.85)),
    1,
  );

  const clickDuck = CLICK_DUCK_FRAMES.reduce(
    (min, center) => Math.min(min, duck(center, 4, 0.75)),
    1,
  );

  const sectionVolume = getMusicSectionVolume(frame);

  const volume = Math.max(
    0,
    Math.min(fadeIn, fadeOut) * sectionVolume * typingDuck * slamDuck * clickDuck,
  );

  return (
    <Audio
      src={staticFile("audio/music.mp3")}
      volume={volume}
      loop
      trimAfter={TOTAL_FRAMES}
    />
  );
};

const DropSfx: React.FC<{ from: number; variant: DropVariant }> = ({
  from,
  variant,
}) => {
  const src =
    variant === "slam"
      ? staticFile("audio/drop-slam.mp3")
      : staticFile("audio/drop-soft.mp3");

  const peak =
    variant === "slam" ? DROP_SLAM_PEAK_VOLUME : DROP_SOFT_PEAK_VOLUME;

  return (
    <Sequence from={from} durationInFrames={DROP_SFX_DURATION} layout="none">
      <Audio
        src={src}
        trimAfter={DROP_SFX_DURATION}
        volume={(f) =>
          interpolate(
            f,
            [0, 2, DROP_SFX_DURATION - 3, DROP_SFX_DURATION],
            [0, peak, peak, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          )
        }
      />
    </Sequence>
  );
};

const ClickSfx: React.FC<{ from: number }> = ({ from }) => (
  <Sequence from={from} durationInFrames={CLICK_SFX_DURATION} layout="none">
    <Audio
      src={staticFile("audio/mouse-click.mp3")}
      trimAfter={CLICK_SFX_DURATION}
      volume={(f) =>
        interpolate(
          f,
          [0, 1, CLICK_SFX_DURATION - 2, CLICK_SFX_DURATION],
          [0, CLICK_SFX_PEAK_VOLUME, CLICK_SFX_PEAK_VOLUME, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  </Sequence>
);

const UiTickSfx: React.FC<{ from: number }> = ({ from }) => (
  <Sequence from={from} durationInFrames={UI_TICK_DURATION} layout="none">
    <Audio
      src={staticFile("audio/ui-tick.mp3")}
      trimAfter={UI_TICK_DURATION}
      volume={(f) =>
        interpolate(
          f,
          [0, 1, UI_TICK_DURATION],
          [0, UI_TICK_PEAK_VOLUME, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  </Sequence>
);

const TransitionSfx: React.FC<{ from: number }> = ({ from }) => (
  <Sequence from={from} durationInFrames={TRANSITION_SFX_DURATION} layout="none">
    <Audio
      src={staticFile("audio/transition-whoosh.mp3")}
      trimAfter={TRANSITION_SFX_DURATION}
      volume={(f) =>
        interpolate(
          f,
          [0, 2, TRANSITION_SFX_DURATION - 2, TRANSITION_SFX_DURATION],
          [0, TRANSITION_SFX_PEAK_VOLUME, TRANSITION_SFX_PEAK_VOLUME, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  </Sequence>
);

export const PicklightPromo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    <Sequence from={SCENES.macbookHero.from} durationInFrames={SCENES.macbookHero.duration}>
      <MacBookHeroScene />
    </Sequence>
    <Sequence from={SCENES.spotlight.from} durationInFrames={SCENES.spotlight.duration} layout="none">
      <SpotlightFailureScene />
    </Sequence>
    <Sequence from={SCENES.mossPlatform.from} durationInFrames={SCENES.mossPlatform.duration} layout="none">
      <MossPlatformScene />
    </Sequence>
    <Sequence from={SCENES.productReveal.from} durationInFrames={SCENES.productReveal.duration} layout="none">
      <ProductRevealScene />
    </Sequence>
    <Sequence from={SCENES.mossDifferentiators.from} durationInFrames={SCENES.mossDifferentiators.duration} layout="none">
      <MossDifferentiatorsScene />
    </Sequence>
    <Sequence from={SCENES.outro.from} durationInFrames={SCENES.outro.duration} layout="none">
      <OutroScene />
    </Sequence>
    <VfxLayer vignette grain />
    <MusicTrack />
    {DROP_SFX.map((event) => (
      <DropSfx key={`${event.frame}-${event.variant}`} from={event.frame} variant={event.variant} />
    ))}
    {CLICK_SFX.map((event) => (
      <ClickSfx key={`click-${event.frame}`} from={event.frame} />
    ))}
    {TRANSITION_SFX_FRAMES.map((frame) => (
      <TransitionSfx key={`whoosh-${frame}`} from={frame} />
    ))}
    {[...spotlightTicks, ...productTicks].map((frame) => (
      <UiTickSfx key={`tick-${frame}`} from={frame} />
    ))}
  </AbsoluteFill>
);
