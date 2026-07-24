import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";

type SequoiaBackdropProps = {
  children?: React.ReactNode;
  scrimOpacity?: number;
  scrimBoost?: number;
  fadeIn?: boolean;
  backdropScale?: number;
};

export const SequoiaBackdrop: React.FC<SequoiaBackdropProps> = ({
  children,
  scrimOpacity = 0.45,
  scrimBoost = 0,
  fadeIn = false,
  backdropScale = 1,
}) => {
  const frame = useCurrentFrame();
  const backdropOpacity = fadeIn
    ? interpolate(frame, [0, 12], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  const effectiveScrim = Math.min(0.65, scrimOpacity + scrimBoost);

  return (
    <AbsoluteFill>
      <Img
        src={staticFile("macbook/macos-wallpaper.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          opacity: backdropOpacity,
          scale: backdropScale,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(180deg, rgba(0,0,0,${effectiveScrim * 0.7}) 0%, rgba(0,0,0,${effectiveScrim}) 50%, rgba(0,0,0,${effectiveScrim * 1.1}) 100%)`,
          opacity: backdropOpacity,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, transparent 30%, rgba(0,0,0,0.5) 100%)",
          opacity: backdropOpacity,
        }}
      />
      {children}
    </AbsoluteFill>
  );
};
