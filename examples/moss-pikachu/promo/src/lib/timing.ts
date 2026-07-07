export const FPS = 30;
export const TOTAL_FRAMES = 1283; // ~42.8 seconds

export const SCENES = {
  macbookHero: { from: 0, duration: 125 },
  spotlight: { from: 125, duration: 162 },
  mossPlatform: { from: 287, duration: 283 },
  productReveal: { from: 570, duration: 225 },
  mossDifferentiators: { from: 795, duration: 283 },
  outro: { from: 1078, duration: 205 },
} as const;

/** Scene boundary frames for transition SFX */
export const SCENE_CUTS = [
  SCENES.spotlight.from,
  SCENES.mossPlatform.from,
  SCENES.productReveal.from,
  SCENES.mossDifferentiators.from,
  SCENES.outro.from,
] as const;
