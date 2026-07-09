import { interpolate, useCurrentFrame } from "remotion";
import { colors } from "../lib/colors";
import { cinematicEase, smoothEase } from "../lib/easing";
import { StepIcon } from "./MacIcons";

export type RailStep = {
  num: string;
  title: string;
  subtitle?: string;
  icon: "folder" | "sparkle" | "check" | "bubble";
};

export type RailTiming = {
  stepWidth: number;
  stepCycle: number;
  zoomInFrames: number;
  zoomMax: number;
  dotStart: number;
  dotEnd: number;
  stepZoomOutStart: number;
  zoomOutStart: number;
  zoomOutEnd: number;
  labelRevealOffset: number;
};

type CinematicZoomRailProps = {
  steps: RailStep[];
  eyebrow: string;
  timing: RailTiming;
  verticalOffset?: number;
};

const stepCenterX = (i: number, stepWidth: number) => i * stepWidth + stepWidth / 2;

export const CinematicZoomRail: React.FC<CinematicZoomRailProps> = ({
  steps,
  eyebrow,
  timing,
  verticalOffset = 0,
}) => {
  const frame = useCurrentFrame();
  const {
    stepWidth,
    stepCycle,
    zoomInFrames,
    zoomMax,
    dotStart,
    dotEnd,
    stepZoomOutStart,
    zoomOutStart,
    zoomOutEnd,
    labelRevealOffset,
  } = timing;

  const railWidth = stepWidth * steps.length;
  const viewportCenter = (1920 - 48 * 2) / 2;
  const lastStep = steps.length - 1;

  const isZoomingOut = frame >= zoomOutStart;
  const activeStep = isZoomingOut
    ? lastStep
    : Math.min(lastStep, Math.floor(frame / stepCycle));
  const phaseFrame = frame - activeStep * stepCycle;

  const zoom = isZoomingOut
    ? interpolate(frame, [zoomOutStart, zoomOutEnd], [zoomMax, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: cinematicEase,
      })
    : phaseFrame <= zoomInFrames
      ? interpolate(phaseFrame, [0, zoomInFrames], [1, zoomMax], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: cinematicEase,
        })
      : phaseFrame >= stepZoomOutStart && activeStep < lastStep
        ? interpolate(phaseFrame, [stepZoomOutStart, stepCycle], [zoomMax, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: cinematicEase,
          })
        : zoomMax;

  const focalX = isZoomingOut
    ? interpolate(frame, [zoomOutStart, zoomOutEnd], [stepCenterX(lastStep, stepWidth), railWidth / 2], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: cinematicEase,
      })
    : phaseFrame >= stepZoomOutStart && activeStep < lastStep
      ? interpolate(
          phaseFrame,
          [stepZoomOutStart, stepCycle],
          [stepCenterX(activeStep, stepWidth), stepCenterX(activeStep + 1, stepWidth)],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: cinematicEase },
        )
      : stepCenterX(activeStep, stepWidth);

  const panX = viewportCenter - focalX;

  const dotProgress =
    !isZoomingOut && phaseFrame >= dotStart && activeStep < lastStep
      ? interpolate(phaseFrame, [dotStart, dotEnd], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: smoothEase,
        })
      : 0;

  const dotX = interpolate(
    dotProgress,
    [0, 1],
    [stepCenterX(activeStep, stepWidth), stepCenterX(activeStep + 1, stepWidth)],
  );

  const dotOpacity =
    dotProgress > 0
      ? phaseFrame >= dotEnd
        ? interpolate(phaseFrame, [dotEnd, stepZoomOutStart], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : 1
      : 0;

  const eyebrowOpacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const railLineOpacity = isZoomingOut
    ? interpolate(frame, [zoomOutStart, zoomOutEnd], [1, 0.55], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  const getEmphasis = (i: number): number => {
    const stepStart = i * stepCycle;

    if (isZoomingOut) {
      return interpolate(frame, [zoomOutStart, zoomOutEnd], [0.85, 0.4], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smoothEase,
      });
    }

    if (frame < stepStart) return 0.28;

    if (activeStep === i) {
      const stepLocal = frame - stepStart;
      return interpolate(stepLocal, [labelRevealOffset, labelRevealOffset + 14], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: smoothEase,
      });
    }

    return i < activeStep ? 0.38 : 0.28;
  };

  return (
    <div
      style={{
        width: "100%",
        height: 540,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: 24 + verticalOffset,
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
          marginBottom: 36,
        }}
      >
        {eyebrow}
      </div>

      <div
        style={{
          position: "relative",
          width: "100%",
          height: 400,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: panX,
            top: "58%",
            width: railWidth,
            translate: "0 -50%",
            scale: zoom,
            transformOrigin: `${focalX}px center`,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 44,
              left: stepWidth / 2,
              right: stepWidth / 2,
              height: 2,
              background: "rgba(255,255,255,0.15)",
              opacity: railLineOpacity,
            }}
          />

          {dotOpacity > 0 && (
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
                opacity: dotOpacity,
              }}
            />
          )}

          <div style={{ display: "flex" }}>
            {steps.map((step, i) => {
              const emphasis = getEmphasis(i);
              const titleSize = interpolate(emphasis, [0, 1], [24, 34], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const subtitleSize = interpolate(emphasis, [0, 1], [15, 18], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              const labelY = interpolate(emphasis, [0, 0.5], [8, 0], {
                extrapolateRight: "clamp",
              });
              const iconScale = interpolate(emphasis, [0, 1], [0.96, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });

              return (
                <div
                  key={step.num}
                  style={{
                    width: stepWidth,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    opacity: emphasis,
                  }}
                >
                  <div
                    style={{
                      width: 80,
                      height: 80,
                      borderRadius: "50%",
                      background: `rgba(255,255,255,${interpolate(emphasis, [0, 1], [0.08, 0.16])})`,
                      border: `1px solid rgba(255,214,10,${interpolate(emphasis, [0, 1], [0.15, 0.55])})`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: 18,
                      scale: iconScale,
                      boxShadow:
                        emphasis > 0.7
                          ? `0 0 28px rgba(255,214,10,${interpolate(emphasis, [0.7, 1], [0, 0.25])})`
                          : "none",
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
                      translate: `0 ${labelY}px`,
                    }}
                  >
                    {step.num}
                  </div>
                  <div
                    style={{
                      fontSize: titleSize,
                      fontWeight: 600,
                      color: colors.white,
                      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                      textAlign: "center",
                      lineHeight: 1.2,
                      padding: "0 16px",
                      minHeight: 74,
                      translate: `0 ${labelY}px`,
                    }}
                  >
                    {step.title}
                  </div>
                  {step.subtitle && (
                    <div
                      style={{
                        fontSize: subtitleSize,
                        fontWeight: 500,
                        color: colors.secondaryText,
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        textAlign: "center",
                        lineHeight: 1.35,
                        padding: "10px 20px 0",
                        maxWidth: 280,
                        minHeight: 52,
                        translate: `0 ${labelY}px`,
                      }}
                    >
                      {step.subtitle}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
