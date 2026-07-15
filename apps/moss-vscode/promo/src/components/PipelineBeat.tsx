import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { slamEase, smoothEase } from "../lib/easing";

type PipelineBeatProps = {
  title: string;
  subtitle: string;
  startFrame: number;
  endFrame: number;
  children: React.ReactNode;
};

export const PipelineBeat: React.FC<PipelineBeatProps> = ({
  title,
  subtitle,
  startFrame,
  endFrame,
  children,
}) => {
  const frame = useCurrentFrame();
  if (frame < startFrame || frame >= endFrame) return null;

  const local = frame - startFrame;
  const duration = endFrame - startFrame;

  const enter = interpolate(local, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  const exit = interpolate(local, [duration - 12, duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const opacity = Math.min(enter, exit);
  const scale = interpolate(local, [0, 14], [0.88, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        scale,
      }}
    >
      <div style={{ marginBottom: 36, position: "relative", zIndex: 1 }}>{children}</div>
      <div
        style={{
          fontSize: 52,
          fontWeight: 700,
          color: colors.white,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          letterSpacing: -1.5,
          textAlign: "center",
          zIndex: 1,
        }}
      >
        {title}
      </div>
      <div
        style={{
          marginTop: 12,
          fontSize: 24,
          fontWeight: 500,
          color: colors.secondaryText,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          textAlign: "center",
          zIndex: 1,
        }}
      >
        {subtitle}
      </div>
    </div>
  );
};

const FILE_NAMES = [
  "auth.ts",
  "retry.ts",
  "session.ts",
  "client.ts",
  "index.ts",
  "config.ts",
  "utils.ts",
  "types.ts",
];

export const ScanVisual: React.FC<{ localFrame: number }> = ({ localFrame }) => {
  return (
    <div style={{ width: 420, height: 220, position: "relative" }}>
      {FILE_NAMES.map((name, i) => {
        const angle = (i / FILE_NAMES.length) * Math.PI * 2 - Math.PI / 2;
        const radius = interpolate(localFrame, [0, 18], [0, 90], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: slamEase,
        });
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius;
        const opacity = interpolate(localFrame, [i * 2, i * 2 + 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={name}
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              translate: `calc(-50% + ${x}px) calc(-50% + ${y}px)`,
              padding: "6px 12px",
              borderRadius: 6,
              background: "rgba(255,255,255,0.1)",
              border: "1px solid rgba(255,214,10,0.35)",
              fontSize: 13,
              color: colors.white,
              fontFamily: '"SF Mono", Menlo, Monaco, monospace',
              opacity,
              whiteSpace: "nowrap",
            }}
          >
            {name}
          </div>
        );
      })}
    </div>
  );
};

export const ChunkVisual: React.FC<{ localFrame: number }> = ({ localFrame }) => {
  const tiles = 6;
  return (
    <div style={{ display: "flex", gap: 10, flexWrap: "wrap", width: 340, justifyContent: "center" }}>
      {Array.from({ length: tiles }).map((_, i) => {
        const delay = i * 3;
        const y = interpolate(localFrame - delay, [0, 16], [40, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: slamEase,
        });
        const opacity = interpolate(localFrame - delay, [0, 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={i}
            style={{
              width: 100,
              height: 56,
              borderRadius: 8,
              background: "rgba(30,30,30,0.9)",
              border: "1px solid rgba(255,255,255,0.15)",
              padding: 8,
              opacity,
              translate: `0 ${y}px`,
            }}
          >
            <div style={{ height: 4, width: "70%", background: "rgba(86,156,214,0.7)", borderRadius: 2, marginBottom: 4 }} />
            <div style={{ height: 4, width: "90%", background: "rgba(206,145,120,0.5)", borderRadius: 2, marginBottom: 4 }} />
            <div style={{ height: 4, width: "50%", background: "rgba(78,201,176,0.5)", borderRadius: 2 }} />
          </div>
        );
      })}
    </div>
  );
};

export const EmbedVisual: React.FC<{ localFrame: number }> = ({ localFrame }) => {
  const collapse = interpolate(localFrame, [0, 22], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  const nodeScale = interpolate(localFrame, [10, 28], [0.4, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });
  const glow = interpolate(localFrame, [18, 40], [0, 0.7], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ width: 280, height: 200, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {[0, 1, 2, 3].map((i) => {
        const ox = ((i % 2) * 2 - 1) * 70 * collapse;
        const oy = (Math.floor(i / 2) * 2 - 1) * 50 * collapse;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              width: 48,
              height: 32,
              borderRadius: 6,
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,214,10,0.3)",
              translate: `${ox}px ${oy}px`,
              opacity: collapse,
            }}
          />
        );
      })}
      <div
        style={{
          width: 88,
          height: 88,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(255,214,10,${0.35 + glow * 0.3}) 0%, rgba(26,61,46,0.9) 70%)`,
          border: "2px solid rgba(255,214,10,0.7)",
          boxShadow: `0 0 ${40 + glow * 40}px rgba(255,214,10,${glow})`,
          scale: nodeScale,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 13,
          fontWeight: 700,
          color: colors.white,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        }}
      >
        local
      </div>
    </div>
  );
};

export const QueryVisual: React.FC<{ localFrame: number }> = ({ localFrame }) => {
  const pulse = interpolate(localFrame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });
  const badge = interpolate(localFrame, [12, 28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: slamEase,
  });

  return (
    <div style={{ width: 280, height: 200, position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
      {[0.4, 0.7, 1].map((r, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: 80 + r * 140 * pulse,
            height: 80 + r * 140 * pulse,
            borderRadius: "50%",
            border: `1px solid rgba(255,214,10,${0.45 - i * 0.12})`,
            opacity: 1 - r * 0.3,
          }}
        />
      ))}
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: "50%",
          background: "rgba(255,214,10,0.2)",
          border: "2px solid rgba(255,214,10,0.8)",
          zIndex: 1,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 12,
          padding: "8px 18px",
          borderRadius: 999,
          background: "rgba(0,0,0,0.55)",
          border: "1px solid rgba(255,214,10,0.55)",
          color: colors.brandYellow,
          fontSize: 28,
          fontWeight: 800,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          letterSpacing: -1,
          opacity: badge,
          scale: interpolate(badge, [0, 1], [0.8, 1]),
        }}
      >
        ~3ms
      </div>
    </div>
  );
};
