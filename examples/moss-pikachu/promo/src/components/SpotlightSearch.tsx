import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { dropEase, smoothEase } from "../lib/easing";
import { materials } from "../lib/materials";
import { MacFileIcon, SpotlightMagnifier, fileVariantFromName } from "./MacIcons";

const WRONG_RESULTS = [
  { name: "rent_calculator.py", type: "Python Script" },
  { name: "lease_template.docx", type: "Document" },
];

type SpotlightSearchProps = {
  query: string;
  showResults?: boolean;
  failed?: boolean;
  shake?: boolean;
  selectedIndex?: number | null;
};

export const SpotlightSearch: React.FC<SpotlightSearchProps> = ({
  query,
  showResults = false,
  failed = false,
  shake = false,
  selectedIndex = null,
}) => {
  const frame = useCurrentFrame();
  const shakeX = shake
    ? interpolate(frame % 6, [0, 2, 4, 6], [0, -5, 5, 0])
    : 0;

  const barDrop = interpolate(frame, [0, 18], [-40, 0], {
    extrapolateRight: "clamp",
    easing: dropEase,
  });

  return (
    <div
      style={{
        width: 680,
        translate: `${shakeX}px ${barDrop}px`,
      }}
    >
      <div
        style={{
          background: materials.spotlight.background,
          backdropFilter: materials.spotlight.backdropFilter,
          borderRadius: 14,
          border: materials.spotlight.border,
          boxShadow: materials.spotlight.boxShadow,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "14px 20px",
            display: "flex",
            alignItems: "center",
            gap: 12,
            borderBottom: showResults ? `1px solid ${colors.glassBorder}` : "none",
          }}
        >
          <SpotlightMagnifier size={22} />
          <div
            style={{
              fontSize: 22,
              color: colors.white,
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              flex: 1,
              fontWeight: 400,
            }}
          >
            {query}
            {!failed && query.length > 0 && (
              <span
                style={{
                  opacity: interpolate(frame % 24, [0, 12, 24], [1, 0, 1]),
                }}
              >
                |
              </span>
            )}
          </div>
        </div>

        {showResults && (
          <div style={{ padding: "8px 0 10px" }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: colors.secondaryText,
                fontFamily: "system-ui, sans-serif",
                padding: "4px 20px 8px",
                textTransform: "uppercase",
                letterSpacing: 0.5,
              }}
            >
              Documents
            </div>
            {WRONG_RESULTS.map((r, i) => {
              const delay = i * 10;
              const localFrame = frame - delay;
              const opacity = interpolate(localFrame, [0, 14], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: smoothEase,
              });
              const y = interpolate(localFrame, [0, 14], [12, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: dropEase,
              });
              const isSelected = selectedIndex === i;
              return (
                <div
                  key={r.name}
                  style={{
                    opacity: failed ? opacity * 0.5 : opacity,
                    translate: `0 ${y}px`,
                    padding: "8px 16px",
                    margin: "0 8px",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    borderRadius: 8,
                    background: isSelected ? "rgba(0, 122, 255, 0.28)" : "transparent",
                  }}
                >
                  <MacFileIcon variant={fileVariantFromName(r.name)} size={32} />
                  <div>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: failed ? colors.secondaryText : colors.white,
                        fontFamily: "system-ui, sans-serif",
                      }}
                    >
                      {r.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: colors.secondaryText,
                        fontFamily: "system-ui, sans-serif",
                        marginTop: 1,
                      }}
                    >
                      {r.type}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
