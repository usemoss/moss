import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { cinematicEase, smoothEase } from "../lib/easing";
import { StepIcon } from "./MacIcons";

const STEPS = [
  { num: "1", label: "Choose folders", icon: "folder" as const },
  { num: "2", label: "Moss hybrid index", icon: "sparkle" as const },
  { num: "3", label: "Ask in plain language", icon: "bubble" as const },
  { num: "4", label: "Open the right file", icon: "check" as const },
];

const STEP_WIDTH = 300;
const RAIL_WIDTH = STEP_WIDTH * STEPS.length;
const VIEWPORT_CENTER = (1920 - 48 * 2) / 2;
const STEP_CYCLE = 42;
const ZOOM_IN_FRAMES = 22;
const ZOOM_OUT_START = STEP_CYCLE * STEPS.length;
const ZOOM_OUT_END = ZOOM_OUT_START + 20;

const stepCenterX = (i: number) => i * STEP_WIDTH + STEP_WIDTH / 2;

export const HowItWorksZoom: React.FC = () => {
  const frame = useCurrentFrame();

  const isZoomingOut = frame >= ZOOM_OUT_START;
  const activeStep = isZoomingOut
    ? 3
    : Math.min(STEPS.length - 1, Math.floor(frame / STEP_CYCLE));
  const phaseFrame = frame - activeStep * STEP_CYCLE;

  const zoom = isZoomingOut
    ? interpolate(frame, [ZOOM_OUT_START, ZOOM_OUT_END], [2.1, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: cinematicEase,
      })
    : interpolate(phaseFrame, [0, ZOOM_IN_FRAMES], [1, 2.1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: cinematicEase,
      });

  const focalX = isZoomingOut
    ? interpolate(frame, [ZOOM_OUT_START, ZOOM_OUT_END], [stepCenterX(3), RAIL_WIDTH / 2], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: cinematicEase,
      })
    : stepCenterX(activeStep);

  const panX = VIEWPORT_CENTER - focalX;

  const dotProgress =
    !isZoomingOut && phaseFrame >= 26 && activeStep < STEPS.length - 1
      ? interpolate(phaseFrame, [26, 36], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        })
      : 0;

  const dotX = interpolate(
    dotProgress,
    [0, 1],
    [stepCenterX(activeStep), stepCenterX(activeStep + 1)],
  );

  const eyebrowOpacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  return (
    <div
      style={{
        width: "100%",
        height: 520,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          fontSize: 28,
          fontWeight: 600,
          letterSpacing: 4,
          color: colors.secondaryText,
          fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          textTransform: "uppercase",
          opacity: eyebrowOpacity,
          marginBottom: 40,
        }}
      >
        How it works
      </div>

      <div
        style={{
          position: "relative",
          width: "100%",
          height: 380,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: panX,
            top: "50%",
            width: RAIL_WIDTH,
            translate: "0 -50%",
            scale: zoom,
            transformOrigin: `${focalX}px center`,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 44,
              left: STEP_WIDTH / 2,
              right: STEP_WIDTH / 2,
              height: 2,
              background: "rgba(255,255,255,0.15)",
            }}
          />

          {dotProgress > 0 && (
            <div
              style={{
                position: "absolute",
                top: 40,
                left: dotX,
                width: 12,
                height: 12,
                borderRadius: "50%",
                background: colors.brandYellow,
                boxShadow: "0 0 14px rgba(255,214,10,0.9)",
                translate: "-50% 0",
                zIndex: 2,
              }}
            />
          )}

          <div style={{ display: "flex" }}>
            {STEPS.map((step, i) => {
              const stepStart = i * STEP_CYCLE;
              const isActive =
                !isZoomingOut && activeStep === i && frame >= stepStart;
              const stepSeen = frame >= stepStart + 8;
              const labelFrame = frame - (stepStart + 8);

              const labelOpacity = isActive
                ? interpolate(labelFrame, [0, 12], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: smoothEase,
                  })
                : isZoomingOut
                  ? 0.9
                  : stepSeen
                    ? 0.65
                    : 0.55;

              const labelY = isActive
                ? interpolate(labelFrame, [0, 12], [10, 0], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: smoothEase,
                  })
                : 0;

              return (
                <div
                  key={step.num}
                  style={{
                    width: STEP_WIDTH,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    opacity: isZoomingOut ? 0.92 : isActive ? 1 : 0.55,
                  }}
                >
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      borderRadius: "50%",
                      background: isActive
                        ? "rgba(255,255,255,0.16)"
                        : "rgba(255,255,255,0.08)",
                      border: `1px solid ${isActive ? "rgba(255,214,10,0.55)" : colors.glassBorder}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 18,
                      boxShadow: isActive ? "0 0 28px rgba(255,214,10,0.25)" : "none",
                    }}
                  >
                    <StepIcon variant={step.icon} size={38} />
                  </div>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 600,
                      color: colors.white,
                      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                      marginBottom: 8,
                      opacity: labelOpacity,
                      translate: `0 ${labelY}px`,
                    }}
                  >
                    {step.num}
                  </div>
                  <div
                    style={{
                      fontSize: isActive ? 34 : 24,
                      fontWeight: 600,
                      color: colors.white,
                      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                      textAlign: "center",
                      lineHeight: 1.2,
                      padding: "0 12px",
                      opacity: labelOpacity,
                      translate: `0 ${labelY}px`,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {step.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
