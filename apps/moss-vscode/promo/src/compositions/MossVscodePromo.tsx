import { Audio } from "@remotion/media";
import { AbsoluteFill, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { VfxLayer } from "../components/VfxLayer";
import { GREP_QUERY, SEMANTIC_QUERY } from "../lib/demo";
import { getMusicSectionVolume } from "../lib/music";
import {
  CLICK_DUCK_FRAMES,
  CLICK_SFX,
  CLICK_SFX_DURATION,
  CLICK_SFX_PEAK_VOLUME,
  DING_SFX_DURATION,
  DING_SFX_FRAMES,
  DING_SFX_PEAK_VOLUME,
  DROP_SFX,
  DROP_SLAM_DURATION,
  DROP_SLAM_PEAK_VOLUME,
  DROP_SOFT_DURATION,
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
import { EditorSuperpowersScene } from "../scenes/EditorSuperpowersScene";
import { GrepFailureScene } from "../scenes/GrepFailureScene";
import { HeroScene } from "../scenes/HeroScene";
import { HowItWorksScene } from "../scenes/HowItWorksScene";
import { OutroScene } from "../scenes/OutroScene";
import { ProductDemoScene } from "../scenes/ProductDemoScene";

const GREP_DUCK = SCENES.grepFailure.from + 20;
const PRODUCT_DUCK = SCENES.productDemo.from + 180;

const grepTicks = getTypingTickFrames(SCENES.grepFailure.from, 12, GREP_QUERY);
const productTicks = getTypingTickFrames(SCENES.productDemo.from, 160, SEMANTIC_QUERY);

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
    duck(GREP_DUCK, 20, 0.72),
    duck(PRODUCT_DUCK, 30, 0.72),
  );

  const slamDuck = SLAM_DUCK_FRAMES.reduce(
    (min, center) => Math.min(min, duck(center, 6, 0.9)),
    1,
  );

  const clickDuck = CLICK_DUCK_FRAMES.reduce(
    (min, center) => Math.min(min, duck(center, 4, 0.85)),
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
      // Full-length bed (~56s) — do not loop; a 30s loop was hard-cutting at ~30s
      trimAfter={TOTAL_FRAMES}
    />
  );
};

/** Remotion.media whip (slam) / whoosh (soft drop) */
const DropSfx: React.FC<{ from: number; variant: DropVariant }> = ({
  from,
  variant,
}) => {
  const isSlam = variant === "slam";
  const src = isSlam
    ? staticFile("audio/whip.wav")
    : staticFile("audio/page-turn.wav");
  const duration = isSlam ? DROP_SLAM_DURATION : DROP_SOFT_DURATION;
  const peak = isSlam ? DROP_SLAM_PEAK_VOLUME : DROP_SOFT_PEAK_VOLUME;

  return (
    <Sequence from={from} durationInFrames={duration} layout="none">
      <Audio
        src={src}
        volume={(f) =>
          interpolate(
            f,
            [0, 1, duration - 2, duration],
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
      src={staticFile("audio/mouse-click-remotion.wav")}
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
      src={staticFile("audio/switch.wav")}
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
      src={staticFile("audio/whoosh.wav")}
      volume={(f) =>
        interpolate(
          f,
          [0, 1, TRANSITION_SFX_DURATION - 2, TRANSITION_SFX_DURATION],
          [0, TRANSITION_SFX_PEAK_VOLUME, TRANSITION_SFX_PEAK_VOLUME, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  </Sequence>
);

const DingSfx: React.FC<{ from: number }> = ({ from }) => (
  <Sequence from={from} durationInFrames={DING_SFX_DURATION} layout="none">
    <Audio
      src={staticFile("audio/ding.wav")}
      volume={(f) =>
        interpolate(
          f,
          [0, 2, DING_SFX_DURATION - 8, DING_SFX_DURATION],
          [0, DING_SFX_PEAK_VOLUME, DING_SFX_PEAK_VOLUME * 0.6, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  </Sequence>
);

export const MossVscodePromo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: "#000" }}>
    <Sequence from={SCENES.hero.from} durationInFrames={SCENES.hero.duration}>
      <HeroScene />
    </Sequence>
    <Sequence from={SCENES.grepFailure.from} durationInFrames={SCENES.grepFailure.duration} layout="none">
      <GrepFailureScene />
    </Sequence>
    <Sequence from={SCENES.howItWorks.from} durationInFrames={SCENES.howItWorks.duration} layout="none">
      <HowItWorksScene />
    </Sequence>
    <Sequence from={SCENES.productDemo.from} durationInFrames={SCENES.productDemo.duration} layout="none">
      <ProductDemoScene />
    </Sequence>
    <Sequence from={SCENES.superpowers.from} durationInFrames={SCENES.superpowers.duration} layout="none">
      <EditorSuperpowersScene />
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
    {[...grepTicks, ...productTicks].map((frame) => (
      <UiTickSfx key={`tick-${frame}`} from={frame} />
    ))}
    {DING_SFX_FRAMES.map((frame) => (
      <DingSfx key={`ding-${frame}`} from={frame} />
    ))}
  </AbsoluteFill>
);
