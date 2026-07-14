import { AbsoluteFill } from "remotion";
import { vscode } from "../../lib/colors";
import { ActivityBar, type ActivityView } from "./ActivityBar";
import { CodeEditorPane } from "./CodeEditorPane";
import { StatusBar, type MossStatus } from "./StatusBar";
import { TabBar, type EditorTab } from "./TabBar";
import { TitleBar } from "./TitleBar";

type VSCodeWindowProps = {
  children?: React.ReactNode;
  /** Sidebar content (Find panel or Moss panel) */
  sidebar?: React.ReactNode;
  activity: ActivityView;
  mossPulse?: boolean;
  tabs: EditorTab[];
  activeTabId: string;
  editorLines: string[];
  highlightLine?: number | null;
  startLineNumber?: number;
  mossStatus?: MossStatus;
  mossLabel?: string;
  floating?: boolean;
  scale?: number;
};

export const VSCodeWindow: React.FC<VSCodeWindowProps> = ({
  sidebar,
  activity,
  mossPulse,
  tabs,
  activeTabId,
  editorLines,
  highlightLine = null,
  startLineNumber = 1,
  mossStatus = "idle",
  mossLabel,
  floating = true,
  scale = 1,
}) => {
  const window = (
    <div
      style={{
        width: 1480,
        height: 900,
        borderRadius: floating ? 10 : 0,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: vscode.editor,
        boxShadow: floating
          ? "0 40px 100px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)"
          : undefined,
        scale,
      }}
    >
      <TitleBar />
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <ActivityBar active={activity} mossPulse={mossPulse} />
        {sidebar}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <TabBar tabs={tabs} activeId={activeTabId} />
          <CodeEditorPane
            lines={editorLines}
            highlightLine={highlightLine}
            startLineNumber={startLineNumber}
          />
        </div>
      </div>
      <StatusBar mossStatus={mossStatus} mossLabel={mossLabel} />
    </div>
  );

  if (!floating) {
    return window;
  }

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        paddingTop: 20,
      }}
    >
      {window}
    </AbsoluteFill>
  );
};
