import { interpolate, useCurrentFrame } from "remotion";
import { dropEase } from "../lib/easing";
import { MacWindowChrome } from "./MacWindowChrome";

const PYTHON_LINES: { text: string; color: string }[] = [
  { text: "# rent_calculator.py", color: "#6a9955" },
  { text: "import math", color: "#c586c0" },
  { text: "", color: "#d4d4d4" },
  { text: "def calc_monthly_rent(base, sqft):", color: "#dcdcaa" },
  { text: "    rate = base * 1.15  # wrong multiplier??", color: "#d4d4d4" },
  { text: "    return rate + (sqft * 0.8)", color: "#d4d4d4" },
  { text: "", color: "#d4d4d4" },
  { text: "# TODO: fix lease calc", color: "#6a9955" },
  { text: "tenant = '???'", color: "#d4d4d4" },
  { text: "deposit = calc_monthly_rent(2400, 850)", color: "#d4d4d4" },
  { text: "print(deposit)  # 3720??", color: "#d4d4d4" },
];

type PythonEditorWindowProps = {
  enterFrame?: number;
  exitFrame?: number;
  zoomFrom?: number;
};

export const PythonEditorWindow: React.FC<PythonEditorWindowProps> = ({
  enterFrame = 0,
  exitFrame = 9999,
  zoomFrom = 0.92,
}) => {
  const frame = useCurrentFrame();
  const localFrame = frame - enterFrame;

  if (frame < enterFrame || frame > exitFrame) return null;

  const opacity = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const scale = interpolate(localFrame, [0, 12], [zoomFrom, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });

  const fadeOut =
    frame > exitFrame - 8
      ? interpolate(frame, [exitFrame - 8, exitFrame], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 20,
        opacity: opacity * fadeOut,
        scale,
      }}
    >
      <MacWindowChrome title="rent_calculator.py">
        <div
          style={{
            height: "100%",
            background: "#1e1e1e",
            padding: "16px 20px",
            fontFamily: "Menlo, Monaco, 'Courier New', monospace",
            fontSize: 13,
            lineHeight: 1.65,
            overflow: "hidden",
          }}
        >
          {PYTHON_LINES.map((line, i) => (
            <div key={i} style={{ display: "flex", gap: 16 }}>
              <span style={{ color: "#858585", width: 20, textAlign: "right", userSelect: "none" }}>
                {i + 1}
              </span>
              <span style={{ color: line.color }}>{line.text || "\u00A0"}</span>
            </div>
          ))}
        </div>
      </MacWindowChrome>
    </div>
  );
};
