import { interpolate, useCurrentFrame } from "remotion";
import { smoothEase } from "../lib/easing";
import { materials } from "../lib/materials";

type IndexingToastProps = {
  startFrame?: number;
};

export const IndexingToast: React.FC<IndexingToastProps> = ({ startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;

  if (local < 0 || local > 45) return null;

  const opacity = interpolate(local, [0, 10, 35, 45], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const progress = interpolate(local, [8, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 36,
        right: 120,
        opacity,
        padding: "10px 14px",
        borderRadius: 12,
        background: materials.panel.background,
        backdropFilter: materials.panel.backdropFilter,
        border: materials.panel.border,
        boxShadow: materials.panel.boxShadow,
        minWidth: 220,
        zIndex: 20,
      }}
    >
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "rgba(255,255,255,0.9)",
          fontFamily: "system-ui, sans-serif",
          marginBottom: 8,
        }}
      >
        Indexing your folders…
      </div>
      <div
        style={{
          height: 4,
          borderRadius: 2,
          background: "rgba(255,255,255,0.12)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${progress * 100}%`,
            background: "linear-gradient(90deg, #34C759, #30D158)",
            borderRadius: 2,
          }}
        />
      </div>
    </div>
  );
};
