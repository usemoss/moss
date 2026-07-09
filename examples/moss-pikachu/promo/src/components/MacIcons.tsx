type MacFileIconProps = {
  variant: "pdf" | "doc" | "txt" | "py";
  size?: number;
};

const FILE_STYLES: Record<
  MacFileIconProps["variant"],
  { bg: string; badge: string; label: string }
> = {
  pdf: { bg: "#e8e8ed", badge: "#ff3b30", label: "PDF" },
  doc: { bg: "#e8e8ed", badge: "#007aff", label: "DOC" },
  txt: { bg: "#e8e8ed", badge: "#8e8e93", label: "TXT" },
  py: { bg: "#e8e8ed", badge: "#ffd60a", label: "PY" },
};

export const MacFileIcon: React.FC<MacFileIconProps> = ({ variant, size = 40 }) => {
  const { bg, badge, label } = FILE_STYLES[variant];
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 8,
        background: bg,
        position: "relative",
        flexShrink: 0,
        boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: size * 0.35,
          height: size * 0.35,
          background: "linear-gradient(135deg, transparent 50%, #d1d1d6 50%)",
          borderTopRightRadius: 8,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 4,
          left: 4,
          right: 4,
          height: size * 0.28,
          background: badge,
          borderRadius: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: size * 0.2,
          fontWeight: 700,
          color: variant === "py" ? "#1c1c1e" : "#fff",
          fontFamily: "system-ui, sans-serif",
          letterSpacing: -0.3,
        }}
      >
        {label}
      </div>
    </div>
  );
};

export const fileVariantFromName = (name: string): MacFileIconProps["variant"] => {
  const ext = name.split(".").pop()?.toLowerCase();
  if (ext === "pdf") return "pdf";
  if (ext === "py") return "py";
  if (ext === "txt") return "txt";
  return "doc";
};

export const SpotlightMagnifier: React.FC<{ size?: number }> = ({ size = 26 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ opacity: 0.85, flexShrink: 0 }}>
    <circle cx="10.5" cy="10.5" r="6.5" stroke="rgba(255,255,255,0.85)" strokeWidth="2" />
    <line x1="15.5" y1="15.5" x2="21" y2="21" stroke="rgba(255,255,255,0.85)" strokeWidth="2" strokeLinecap="round" />
  </svg>
);

type StepIconProps = {
  variant: "folder" | "sparkle" | "bubble" | "check";
  size?: number;
  color?: string;
};

export const StepIcon: React.FC<StepIconProps> = ({
  variant,
  size = 36,
  color = "rgba(255,255,255,0.9)",
}) => {
  const stroke = color;
  const sw = 1.8;
  switch (variant) {
    case "folder":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <path
            d="M3 7.5A1.5 1.5 0 014.5 6H9l2 2h8.5A1.5 1.5 0 0121 9.5v9A1.5 1.5 0 0119.5 20h-15A1.5 1.5 0 013 18.5v-11z"
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
        </svg>
      );
    case "sparkle":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2l1.8 5.5L19 9.2l-5.2 1.7L12 16.4l-1.8-5.5L5 9.2l5.2-1.7L12 2z"
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
        </svg>
      );
    case "bubble":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <path
            d="M5 5.5A2.5 2.5 0 017.5 3h9A2.5 2.5 0 0119 5.5v7A2.5 2.5 0 0116.5 15H10l-4 4v-4H7.5A2.5 2.5 0 015 12.5v-7z"
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
        </svg>
      );
    case "check":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9" stroke={stroke} strokeWidth={sw} />
          <path d="M8 12l3 3 5-6" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
};
