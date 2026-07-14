import { interpolate } from "remotion";
import { SCENES } from "./timing";

/** Louder bed so music is clearly present under SFX throughout */
const baseVolume = (frame: number): number =>
  interpolate(
    frame,
    [
      0,
      SCENES.howItWorks.from,
      SCENES.productDemo.from,
      SCENES.superpowers.from,
      SCENES.outro.from,
      SCENES.outro.from + SCENES.outro.duration,
    ],
    // Keep second half steady — avoid a volume jump after the old 30s loop point
    [0.55, 0.6, 0.62, 0.58, 0.56, 0.6],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

const outroBoost = (frame: number): number =>
  interpolate(
    frame,
    [SCENES.outro.from, SCENES.outro.from + 30, SCENES.outro.from + SCENES.outro.duration],
    [1, 1.15, 1.2],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

/** Section-based base volume — peaks at product, calmer mid, swell outro */
export const getMusicSectionVolume = (frame: number): number =>
  frame >= SCENES.outro.from ? baseVolume(frame) * outroBoost(frame) : baseVolume(frame);
