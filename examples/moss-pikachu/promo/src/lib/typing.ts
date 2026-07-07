/** Variable-speed typing with pause after "Bradley's" */
export const getTypedLength = (
  frame: number,
  startFrame: number,
  text: string,
): number => {
  if (frame < startFrame) return 0;

  let chars = 0;
  let f = startFrame;
  const pauseAfter = "Bradley's".length;

  for (let i = 0; i < text.length; i++) {
    if (frame < f) break;
    chars = i + 1;
    const interval = i === pauseAfter - 1 ? 6 : i < 3 ? 3 : 2;
    f += interval;
  }

  return Math.min(text.length, chars);
};
