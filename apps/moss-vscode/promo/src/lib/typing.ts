/** Variable-speed typing with optional pause after a prefix */
export const getTypedLength = (
  frame: number,
  startFrame: number,
  text: string,
  pauseAfter?: string,
): number => {
  if (frame < startFrame) return 0;

  let chars = 0;
  let f = startFrame;
  const pauseLen = pauseAfter?.length ?? -1;

  for (let i = 0; i < text.length; i++) {
    if (frame < f) break;
    chars = i + 1;
    const interval = i === pauseLen - 1 ? 6 : i < 3 ? 3 : 2;
    f += interval;
  }

  return Math.min(text.length, chars);
};
