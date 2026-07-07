import { SCENE_CUTS, SCENES } from "./timing";

export type DropVariant = "slam" | "drop";

export type DropSfxEvent = {
  frame: number;
  variant: DropVariant;
};

const mossRailDrops = (sceneFrom: number) => [
  { frame: sceneFrom + 8, variant: "slam" as const },
  { frame: sceneFrom + 68, variant: "drop" as const },
  { frame: sceneFrom + 128, variant: "drop" as const },
  { frame: sceneFrom + 188, variant: "drop" as const },
];

/** Absolute-frame drop/slam SFX synced to headline animations. */
export const DROP_SFX: DropSfxEvent[] = [
  { frame: SCENES.macbookHero.from + 8, variant: "slam" },
  { frame: SCENES.macbookHero.from + 42, variant: "drop" },
  ...mossRailDrops(SCENES.mossPlatform.from),
  { frame: SCENES.productReveal.from + 4, variant: "drop" },
  ...mossRailDrops(SCENES.mossDifferentiators.from),
  { frame: SCENES.outro.from + 22, variant: "slam" },
  { frame: SCENES.outro.from + 55, variant: "drop" },
];

export const TRANSITION_SFX_FRAMES = [...SCENE_CUTS];

export const DROP_SFX_DURATION = 10;
export const DROP_SLAM_PEAK_VOLUME = 0.42;
export const DROP_SOFT_PEAK_VOLUME = 0.3;
export const TRANSITION_SFX_DURATION = 6;
export const TRANSITION_SFX_PEAK_VOLUME = 0.32;
export const UI_TICK_DURATION = 3;
export const UI_TICK_PEAK_VOLUME = 0.35;

/** Slam hits duck music slightly (lighter than typing duck). */
export const SLAM_DUCK_FRAMES = DROP_SFX.filter((e) => e.variant === "slam").map(
  (e) => e.frame,
);

export type ClickSfxEvent = { frame: number };

/** UI click moments */
export const CLICK_SFX: ClickSfxEvent[] = [
  { frame: SCENES.spotlight.from + 0 },
  { frame: SCENES.spotlight.from + 50 },
  { frame: SCENES.spotlight.from + 73 },
  { frame: SCENES.productReveal.from + 25 },
  { frame: SCENES.productReveal.from + 90 },
  { frame: SCENES.productReveal.from + 130 },
];

export const CLICK_SFX_DURATION = 6;
export const CLICK_SFX_PEAK_VOLUME = 0.74;
export const CLICK_DUCK_FRAMES = CLICK_SFX.map((e) => e.frame);

/** Frames where UI tick SFX plays during typing */
export const getTypingTickFrames = (
  sceneFrom: number,
  startFrame: number,
  text: string,
): number[] => {
  const frames: number[] = [];
  let f = sceneFrom + startFrame;
  const pauseAfter = "Bradley's".length;

  for (let i = 0; i < text.length; i++) {
    frames.push(f);
    const interval = i === pauseAfter - 1 ? 6 : i < 3 ? 3 : 2;
    f += interval;
  }

  return frames;
};
