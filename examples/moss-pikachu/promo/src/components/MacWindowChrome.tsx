type MacWindowChromeProps = {
  title: string;
  children: React.ReactNode;
  width?: number | string;
  height?: number | string;
};

export const MacWindowChrome: React.FC<MacWindowChromeProps> = ({
  title,
  children,
  width = "88%",
  height = "78%",
}) => (
  <div
    style={{
      width,
      height,
      borderRadius: 10,
      overflow: "hidden",
      boxShadow: "0 24px 64px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.08)",
      display: "flex",
      flexDirection: "column",
    }}
  >
    <div
      style={{
        height: 36,
        background: "linear-gradient(180deg, #3a3a3c 0%, #2c2c2e 100%)",
        display: "flex",
        alignItems: "center",
        padding: "0 14px",
        gap: 8,
        flexShrink: 0,
      }}
    >
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
      <div
        style={{
          flex: 1,
          textAlign: "center",
          fontSize: 13,
          color: "rgba(255,255,255,0.75)",
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          fontWeight: 500,
          marginRight: 52,
        }}
      >
        {title}
      </div>
    </div>
    <div style={{ flex: 1, overflow: "hidden" }}>{children}</div>
  </div>
);
