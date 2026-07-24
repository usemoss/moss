import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { MossSidebarPanel } from "../components/MossSidebarPanel";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { VSCodeWindow } from "../components/vscode/VSCodeWindow";
import {
  DEMO_HITS,
  HIGHLIGHT_LINE,
  RETRY_TS_LINES,
  SEMANTIC_QUERY,
} from "../lib/demo";
import { smoothEase } from "../lib/easing";
import { SCENES } from "../lib/timing";
import { getTypedLength } from "../lib/typing";
import { type } from "../lib/typography";

const BASE_TABS = [
  { id: "session", label: "session.ts" },
  { id: "client", label: "client.ts" },
];

const PLACEHOLDER_LINES = [
  "import { refreshSession } from './session';",
  "",
  "export function createApiClient(baseUrl: string) {",
  "  return {",
  "    async get(path: string) {",
  "      return fetch(`${baseUrl}${path}`);",
  "    },",
  "  };",
  "}",
];

export const ProductDemoScene: React.FC = () => {
  const frame = useCurrentFrame();

  // Timeline (local frames within 450f scene):
  // 0-30: caption + moss icon pulse
  // 30-50: sidebar opens (moss active)
  // 50-70: Create Index press
  // 70-140: indexing progress
  // 140-160: ready
  // 160-260: type query
  // 260-300: results appear
  // 300-340: select first result
  // 340-450: editor jump + hold

  const mossPulse = frame >= 10 && frame < 45;
  const showMossSidebar = frame >= 30;
  const createPressed = frame >= 50 && frame < 70;

  let indexState: "unindexed" | "indexing" | "ready" = "unindexed";
  let indexProgress: string | undefined;
  let mossStatus: "idle" | "indexing" | "ready" = "idle";
  let mossLabel: string | undefined;

  if (frame >= 70 && frame < 140) {
    indexState = "indexing";
    mossStatus = "indexing";
    const done = Math.min(1203, Math.floor(interpolate(frame, [70, 140], [0, 1203], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })));
    indexProgress = `${done}/1203`;
    mossLabel = `Moss: indexing ${done}/1203`;
  } else if (frame >= 140) {
    indexState = "ready";
    mossStatus = "ready";
    mossLabel = "Moss: 1,203 chunks";
  }

  const typingStart = 160;
  const typedLength =
    indexState === "ready" ? getTypedLength(frame, typingStart, SEMANTIC_QUERY) : 0;
  const query = SEMANTIC_QUERY.slice(0, typedLength);

  const showResults = frame >= 260 && typedLength >= SEMANTIC_QUERY.length;
  const visibleHitCount =
    frame < 270 ? 1 : frame < 285 ? 2 : 3;
  const selectedIndex = frame >= 300 ? 0 : null;
  const jumped = frame >= 340;

  const tabs = jumped
    ? [...BASE_TABS, { id: "retry", label: "retry.ts" }]
    : BASE_TABS;
  const activeTabId = jumped ? "retry" : "client";
  const editorLines = jumped ? RETRY_TS_LINES : PLACEHOLDER_LINES;
  const highlightLine = jumped ? HIGHLIGHT_LINE : null;
  const startLineNumber = jumped ? 35 : 1;

  const captionOpacity = interpolate(frame, [0, 12, 40, 55], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: smoothEase,
  });

  const searchByMeaningOpacity = interpolate(
    frame,
    [145, 160, 200, 220],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: smoothEase,
    },
  );

  return (
    <SequoiaBackdrop scrimOpacity={0.4}>
      <SceneBridge sceneDuration={SCENES.productDemo.duration} exitDuration={15}>
        <AbsoluteFill
          style={{
            justifyContent: "flex-start",
            alignItems: "center",
            paddingTop: 28,
            opacity: captionOpacity,
            zIndex: 2,
          }}
        >
          <div
            style={{
              fontSize: type.subhead,
              fontWeight: 600,
              color: "rgba(255,255,255,0.8)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -0.5,
            }}
          >
            Moss Code Search
          </div>
        </AbsoluteFill>

        <AbsoluteFill
          style={{
            justifyContent: "flex-start",
            alignItems: "center",
            paddingTop: 28,
            opacity: searchByMeaningOpacity,
            zIndex: 2,
          }}
        >
          <div
            style={{
              fontSize: type.subhead,
              fontWeight: 600,
              color: "rgba(255,255,255,0.75)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              letterSpacing: -0.5,
            }}
          >
            Search by meaning.
          </div>
        </AbsoluteFill>

        <AbsoluteFill style={{ paddingTop: 20 }}>
          <VSCodeWindow
            activity={showMossSidebar ? "moss" : "explorer"}
            mossPulse={mossPulse}
            tabs={tabs}
            activeTabId={activeTabId}
            editorLines={editorLines}
            highlightLine={highlightLine}
            startLineNumber={startLineNumber}
            mossStatus={mossStatus}
            mossLabel={mossLabel}
            scale={0.92}
            sidebar={
              showMossSidebar ? (
                <MossSidebarPanel
                  query={query}
                  hits={DEMO_HITS}
                  showResults={showResults}
                  selectedIndex={selectedIndex}
                  indexState={indexState}
                  indexProgress={indexProgress}
                  createIndexPressed={createPressed}
                  visibleHitCount={visibleHitCount}
                  resultsFromFrame={260}
                />
              ) : undefined
            }
          />
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
