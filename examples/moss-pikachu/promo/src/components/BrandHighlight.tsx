import { colors } from "../lib/colors";

type BrandHighlightProps = {
  children: React.ReactNode;
  fontSize?: number;
  fontWeight?: number;
  withScrim?: boolean;
};

export const BrandHighlight: React.FC<BrandHighlightProps> = ({
  children,
  fontSize,
  fontWeight = 700,
  withScrim = false,
}) => (
  <span style={{ position: "relative", display: "inline-block" }}>
    {withScrim && (
      <span
        style={{
          position: "absolute",
          inset: "-20px -40px",
          borderRadius: 24,
          background: "radial-gradient(ellipse, rgba(0,0,0,0.55) 0%, transparent 70%)",
          zIndex: 0,
        }}
      />
    )}
    <span
      style={{
        position: "relative",
        zIndex: 1,
        color: colors.brandYellow,
        fontSize,
        fontWeight,
        textShadow: colors.brandYellowHalo,
      }}
    >
      {children}
    </span>
  </span>
);
