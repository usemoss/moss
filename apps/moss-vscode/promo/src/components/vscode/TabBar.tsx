import { vscode } from "../../lib/colors";

export type EditorTab = {
  id: string;
  label: string;
  dirty?: boolean;
};

type TabBarProps = {
  tabs: EditorTab[];
  activeId: string;
};

export const TabBar: React.FC<TabBarProps> = ({ tabs, activeId }) => (
  <div
    style={{
      height: 35,
      background: vscode.tabBar,
      display: "flex",
      alignItems: "stretch",
      flexShrink: 0,
      borderBottom: `1px solid ${vscode.border}`,
      overflow: "hidden",
    }}
  >
    {tabs.map((tab) => {
      const active = tab.id === activeId;
      return (
        <div
          key={tab.id}
          style={{
            minWidth: 120,
            maxWidth: 180,
            padding: "0 14px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            background: active ? vscode.activeTab : "transparent",
            borderRight: `1px solid ${vscode.border}`,
            borderTop: active ? "1px solid #007acc" : "1px solid transparent",
            fontSize: 13,
            color: active ? "#ffffff" : "#969696",
            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
          }}
        >
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
          >
            {tab.label}
            {tab.dirty ? " ●" : ""}
          </span>
          <span style={{ opacity: 0.5, fontSize: 14, lineHeight: 1 }}>×</span>
        </div>
      );
    })}
  </div>
);
