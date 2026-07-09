import { interpolate, useCurrentFrame } from "remotion";
import { WINNING_FILE, WINNING_SNIPPET } from "../lib/demo";
import { dropEase } from "../lib/easing";
import { MacWindowChrome } from "./MacWindowChrome";

const HANDWRITING = "Bradley Hand, Snell Roundhand, Caveat, cursive";

const SCRIBBLE_LINES = [
  "M 40 120 Q 80 115 120 118 T 200 120 T 280 117 T 360 119",
  "M 40 145 Q 100 140 160 148 T 280 143 T 360 146",
  "M 40 170 Q 60 168 90 172 T 150 169 T 220 171 T 300 168 T 360 170",
  "M 40 195 Q 120 192 200 198 T 360 194",
  "M 40 220 Q 80 218 130 222 T 220 219 T 360 221",
  "M 40 245 Q 150 242 260 247 T 360 244",
  "M 40 270 Q 90 268 140 272 T 240 269 T 360 271",
  "M 40 295 Q 110 293 180 297 T 300 294 T 360 296",
];

type PdfPreviewWindowProps = {
  enterFrame?: number;
};

export const PdfPreviewWindow: React.FC<PdfPreviewWindowProps> = ({ enterFrame = 0 }) => {
  const frame = useCurrentFrame();
  const localFrame = frame - enterFrame;

  if (frame < enterFrame) return null;

  const opacity = interpolate(localFrame, [0, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });
  const scale = interpolate(localFrame, [0, 14], [0.94, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: dropEase,
  });

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 20,
        opacity,
        scale,
      }}
    >
      <MacWindowChrome title={WINNING_FILE} width="90%" height="82%">
        <div
          style={{
            height: "100%",
            background: "#e8e8ed",
            padding: 24,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 2,
              boxShadow: "0 2px 12px rgba(0,0,0,0.12)",
              padding: "36px 44px",
              height: "100%",
              position: "relative",
              fontFamily: "Georgia, 'Times New Roman', serif",
            }}
          >
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                textAlign: "center",
                marginBottom: 28,
                letterSpacing: 0.5,
                color: "#1c1c1e",
              }}
            >
              RESIDENTIAL LEASE AGREEMENT — 2024
            </div>

            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#34C759",
                marginBottom: 12,
                padding: "6px 10px",
                background: "rgba(52,199,89,0.12)",
                borderRadius: 6,
                fontFamily: "system-ui, sans-serif",
              }}
            >
              Match: {WINNING_SNIPPET}
            </div>

            <div style={{ fontSize: 11, color: "#8e8e93", marginBottom: 16 }}>
              This Agreement is entered into between Landlord and Tenant effective January 1, 2024…
            </div>

            <svg
              width="100%"
              height={200}
              viewBox="0 0 400 320"
              style={{ marginBottom: 12 }}
            >
              {SCRIBBLE_LINES.map((d, i) => (
                <path
                  key={i}
                  d={d}
                  fill="none"
                  stroke="#c7c7cc"
                  strokeWidth={2}
                  strokeLinecap="round"
                />
              ))}
            </svg>

            <div style={{ fontSize: 11, color: "#aeaeb2", lineHeight: 1.8 }}>
              <p style={{ margin: "0 0 8px" }}>
                Tenant agrees to pay monthly rent of $2,400.00 for the premises located at…
              </p>
              <p style={{ margin: 0 }}>
                Security deposit shall be equal to one month&apos;s rent. Term: 12 months…
              </p>
            </div>

            <div
              style={{
                position: "absolute",
                right: 32,
                top: 180,
                fontFamily: HANDWRITING,
                fontSize: 22,
                color: "#ff3b30",
                transform: "rotate(-8deg)",
              }}
            >
              sign here??
            </div>
            <div
              style={{
                position: "absolute",
                left: 48,
                bottom: 48,
                fontFamily: HANDWRITING,
                fontSize: 28,
                color: "#ff3b30",
                transform: "rotate(3deg)",
              }}
            >
              ???
            </div>
            <svg
              style={{ position: "absolute", right: 60, bottom: 60 }}
              width={80}
              height={30}
              viewBox="0 0 80 30"
            >
              <path
                d="M 4 20 Q 20 8 40 18 T 76 14"
                fill="none"
                stroke="#ff3b30"
                strokeWidth={2.5}
                strokeLinecap="round"
              />
            </svg>
          </div>
        </div>
      </MacWindowChrome>
    </div>
  );
};
