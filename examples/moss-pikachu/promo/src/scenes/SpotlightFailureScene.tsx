import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { MacScreen } from "../components/MacChrome";
import { PythonEditorWindow } from "../components/PythonEditorWindow";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SpotlightSearch } from "../components/SpotlightSearch";
import { SEMANTIC_QUERY } from "../lib/demo";
import { SCENES } from "../lib/timing";
import { getTypedLength } from "../lib/typing";

export const SpotlightFailureScene: React.FC = () => {
  const frame = useCurrentFrame();
  const typedLength = getTypedLength(frame, 15, SEMANTIC_QUERY);
  const query = frame < 15 ? "" : SEMANTIC_QUERY.slice(0, typedLength);
  const showResults = frame > 50;
  const shake = frame >= 68 && frame < 76;
  const selectedIndex = frame >= 70 && frame < 158 ? 0 : null;
  const showPythonEditor = frame >= 76 && frame < 158;
  const failed = showPythonEditor;

  const spotlightScale = showPythonEditor
    ? interpolate(frame, [76, 88], [1, 0.92], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  const spotlightOpacity = showPythonEditor
    ? interpolate(frame, [76, 88], [1, 0.35], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  return (
    <SequoiaBackdrop scrimOpacity={0.4}>
      <SceneBridge sceneDuration={SCENES.spotlight.duration} exitDuration={15} blurOnExit>
        <MacScreen showPet={false}>
          <AbsoluteFill
            style={{
              justifyContent: "flex-start",
              alignItems: "center",
              paddingTop: 120,
              opacity: spotlightOpacity,
              scale: spotlightScale,
            }}
          >
            <SpotlightSearch
              query={query}
              showResults={showResults}
              failed={failed}
              shake={shake}
              selectedIndex={selectedIndex}
            />
          </AbsoluteFill>
          {showPythonEditor && (
            <PythonEditorWindow enterFrame={76} exitFrame={158} zoomFrom={0.88} />
          )}
        </MacScreen>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
