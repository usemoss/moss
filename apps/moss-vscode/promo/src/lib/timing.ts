export const FPS = 30;
/** ~50s — how-it-works + superpowers + crash outro */
export const TOTAL_FRAMES = 1496;

export const HOW_IT_WORKS_DURATION = 283;
export const SUPERPOWERS_DURATION = 283;

export const SCENES = {
  hero: { from: 0, duration: 120 },
  grepFailure: { from: 120, duration: 180 },
  howItWorks: { from: 300, duration: HOW_IT_WORKS_DURATION },
  productDemo: { from: 583, duration: 410 },
  superpowers: { from: 993, duration: SUPERPOWERS_DURATION },
  outro: { from: 1276, duration: 220 },
} as const;

/** Scene boundary frames for transition SFX */
export const SCENE_CUTS = [
  SCENES.grepFailure.from,
  SCENES.howItWorks.from,
  SCENES.productDemo.from,
  SCENES.superpowers.from,
  SCENES.outro.from,
] as const;
