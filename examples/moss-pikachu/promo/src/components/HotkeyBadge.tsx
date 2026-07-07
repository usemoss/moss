import { interpolate, useCurrentFrame } from "remotion";
import { smoothEase } from "../lib/easing";

type HotkeyBadgeProps = {
  pulse?: boolean;
  opacity?: number;
};

const Key: React.FC<{ label: string }> = ({ label }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      minWidth: 28,
      height: 28,
      padding: "0 8px",
      borderRadius: 6,
      background: "rgba(255,255,255,0.14)",
      border: "1px solid rgba(255,255,255,0.25)",
      fontSize: 14,
      fontWeight: 600,
      color: "rgba(255,255,255,0.92)",
      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      boxShadow: "0 2px 0 rgba(0,0,0,0.25)",
    }}
  >
    {label}
  </span>
);

export const HotkeyBadge: React.FC<HotkeyBadgeProps> = ({
  pulse = false,
  opacity = 1,
}) => {
  const frame = useCurrentFrame();
  const scale = pulse
    ? interpolate(frame % 20, [0, 10, 20], [1, 1.06, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smoothEase,
      })
    : 1;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        opacity,
        scale,
      }}
    >
      <Key label="⌘" />
      <Key label="⇧" />
      <Key label="M" />
    </div>
  );
};
