import { interpolate } from "remotion";
import { SCENES } from "./timing";

const baseVolume = (frame: number): number =>
  interpolate(
    frame,
    [
      0,
      SCENES.mossPlatform.from,
      SCENES.productReveal.from,
      SCENES.mossDifferentiators.from,
      SCENES.outro.from,
      SCENES.outro.from + SCENES.outro.duration,
    ],
    [0.38, 0.48, 0.52, 0.46, 0.44, 0.46],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

const outroBoost = (frame: number): number =>
  interpolate(
    frame,
    [SCENES.outro.from, SCENES.outro.from + 30, SCENES.outro.from + SCENES.outro.duration],
    [1, 1.35, 1.45],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

/** Section-based base volume — peaks at product, calmer mid, swell outro */
export const getMusicSectionVolume = (frame: number): number =>
  frame >= SCENES.outro.from ? baseVolume(frame) * outroBoost(frame) : baseVolume(frame);
