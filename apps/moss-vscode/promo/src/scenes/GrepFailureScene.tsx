import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { FindInFilesPanel } from "../components/vscode/FindInFilesPanel";
import { VSCodeWindow } from "../components/vscode/VSCodeWindow";
import {
  GREP_NOISE_RESULTS,
  GREP_QUERY,
  WRONG_FILE_LINES,
} from "../lib/demo";
import { smoothEase } from "../lib/easing";
import { SCENES } from "../lib/timing";
import { getTypedLength } from "../lib/typing";
import { type } from "../lib/typography";

const DEFAULT_TABS = [
  { id: "client", label: "client.ts" },
  { id: "session", label: "session.ts" },
];

const PLACEHOLDER_LINES = [
  "import { createClient } from './http';",
  "",
  "export async function getUser(id: string) {",
  "  return createClient().get(`/users/${id}`);",
  "}",
];

export const GrepFailureScene: React.FC = () => {
  const frame = useCurrentFrame();
  const typedLength = getTypedLength(frame, 12, GREP_QUERY);
  const query = frame < 12 ? "" : GREP_QUERY.slice(0, typedLength);
  const showResults = frame > 55;
  const selectedIndex = frame >= 90 && frame < 170 ? 0 : null;
  const showWrongFile = frame >= 95;
  const shake = frame >= 95 && frame < 105;

  const captionOpacity = interpolate(frame, [8, 20, 150, 170], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const shakeX =
    shake
      ? interpolate(frame, [95, 97, 99, 101, 103, 105], [0, -6, 6, -4, 3, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  const tabs = showWrongFile
    ? [
        ...DEFAULT_TABS,
        { id: "changelog", label: "changelog.md" },
      ]
    : DEFAULT_TABS;

  const activeTabId = showWrongFile ? "changelog" : "client";
  const editorLines = showWrongFile ? WRONG_FILE_LINES : PLACEHOLDER_LINES;
  const highlightLine = showWrongFile ? 3 : null;

  return (
    <SequoiaBackdrop scrimOpacity={0.4}>
      <SceneBridge sceneDuration={SCENES.grepFailure.duration} exitDuration={15} blurOnExit>
        <AbsoluteFill
          style={{
            justifyContent: "flex-start",
            alignItems: "center",
            paddingTop: 36,
            opacity: captionOpacity,
          }}
        >
          <div
            style={{
              fontSize: type.subhead,
              fontWeight: 600,
              color: "rgba(255,255,255,0.75)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -0.5,
              zIndex: 2,
            }}
          >
            Still grepping for concepts?
          </div>
        </AbsoluteFill>

        <AbsoluteFill style={{ translate: `${shakeX}px 0`, paddingTop: 28 }}>
          <VSCodeWindow
            activity="search"
            tabs={tabs}
            activeTabId={activeTabId}
            editorLines={editorLines}
            highlightLine={highlightLine}
            startLineNumber={showWrongFile ? 1 : 1}
            scale={0.92}
            sidebar={
              <FindInFilesPanel
                query={query}
                results={GREP_NOISE_RESULTS}
                showResults={showResults}
                selectedIndex={selectedIndex}
              />
            }
          />
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
