import type { RailTiming } from "../components/CinematicZoomRail";

/** Shared pacing for Moss platform + Why Moss zoom rails (4 × 60f steps + 22f zoom-out). */
export const MOSS_RAIL_TIMING: RailTiming = {
  stepWidth: 320,
  stepCycle: 60,
  zoomInFrames: 22,
  zoomMax: 2,
  dotStart: 30,
  dotEnd: 42,
  stepZoomOutStart: 48,
  zoomOutStart: 240,
  zoomOutEnd: 262,
  labelRevealOffset: 6,
};

export const MOSS_RAIL_SCENE_DURATION = 283;
