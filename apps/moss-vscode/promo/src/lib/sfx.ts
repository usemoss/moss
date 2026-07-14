import { SCENE_CUTS, SCENES } from "./timing";

export type DropVariant = "slam" | "drop";

export type DropSfxEvent = {
  frame: number;
  variant: DropVariant;
};

const pipelineDrops = (sceneFrom: number) => [
  { frame: sceneFrom + 6, variant: "slam" as const },
  { frame: sceneFrom + 70, variant: "drop" as const },
  { frame: sceneFrom + 140, variant: "drop" as const },
  { frame: sceneFrom + 210, variant: "drop" as const },
];

const superpowerDrops = (sceneFrom: number) => [
  // Fewer hits after the music bed's former loop point — keep it clean
  { frame: sceneFrom + 18, variant: "drop" as const },
  { frame: sceneFrom + 58, variant: "drop" as const },
  { frame: sceneFrom + 100, variant: "slam" as const },
];

/** Absolute-frame drop/slam SFX synced to headline animations. */
export const DROP_SFX: DropSfxEvent[] = [
  { frame: SCENES.hero.from + 8, variant: "slam" },
  { frame: SCENES.hero.from + 42, variant: "drop" },
  ...pipelineDrops(SCENES.howItWorks.from),
  { frame: SCENES.productDemo.from + 4, variant: "drop" },
  ...superpowerDrops(SCENES.superpowers.from),
  { frame: SCENES.outro.from + 28, variant: "slam" },
  { frame: SCENES.outro.from + 55, variant: "drop" },
];

export const TRANSITION_SFX_FRAMES = [...SCENE_CUTS];

/** Remotion.media SFX (downloaded to public/audio) — durations at 30fps */
export const DROP_SLAM_DURATION = 8; // whip ~0.17s
export const DROP_SOFT_DURATION = 8; // whoosh / page-turn
export const DROP_SLAM_PEAK_VOLUME = 0.48;
export const DROP_SOFT_PEAK_VOLUME = 0.32;
export const TRANSITION_SFX_DURATION = 8;
export const TRANSITION_SFX_PEAK_VOLUME = 0.32;
export const UI_TICK_DURATION = 6; // switch
export const UI_TICK_PEAK_VOLUME = 0.22;
export const CLICK_SFX_DURATION = 12; // mouse-click ~0.4s
export const CLICK_SFX_PEAK_VOLUME = 0.55;
export const DING_SFX_DURATION = 30;
export const DING_SFX_PEAK_VOLUME = 0.38;

/** Ding on index-ready + outro lockup */
export const DING_SFX_FRAMES = [
  SCENES.productDemo.from + 140,
  SCENES.outro.from + 55,
];

/** Slam hits duck music slightly */
export const SLAM_DUCK_FRAMES = DROP_SFX.filter((e) => e.variant === "slam").map(
  (e) => e.frame,
);

export type ClickSfxEvent = { frame: number };

/** UI click moments */
export const CLICK_SFX: ClickSfxEvent[] = [
  { frame: SCENES.grepFailure.from + 8 },
  { frame: SCENES.grepFailure.from + 55 },
  { frame: SCENES.grepFailure.from + 95 },
  { frame: SCENES.productDemo.from + 35 },
  { frame: SCENES.productDemo.from + 70 },
  { frame: SCENES.productDemo.from + 280 },
];

export const CLICK_DUCK_FRAMES = CLICK_SFX.map((e) => e.frame);

/** Sparse typing ticks — every 3rd character so it doesn't machine-gun */
export const getTypingTickFrames = (
  sceneFrom: number,
  startFrame: number,
  text: string,
): number[] => {
  const frames: number[] = [];
  let f = sceneFrom + startFrame;

  for (let i = 0; i < text.length; i++) {
    if (i % 3 === 0) {
      frames.push(f);
    }
    const interval = i < 3 ? 3 : 2;
    f += interval;
  }

  return frames;
};
