import { colors } from "../lib/colors";

type PicklightWordmarkProps = {
  size?: number;
  variant?: "default" | "large";
};

/** Typography wordmark — Pick (spotlight yellow) + light */
export const PicklightWordmark: React.FC<PicklightWordmarkProps> = ({
  size = 28,
  variant = "default",
}) => {
  const fontSize = variant === "large" ? size * 1.8 : size;
  const weight = variant === "large" ? 800 : 700;

  return (
    <div
      style={{
        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
        fontSize,
        fontWeight: weight,
        letterSpacing: variant === "large" ? -2 : -1,
        lineHeight: 1,
      }}
    >
      <span style={{ color: colors.brandYellow, textShadow: colors.brandYellowHalo }}>
        Pick
      </span>
      <span style={{ color: colors.white }}>light</span>
    </div>
  );
};
