import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { vscode } from "../lib/colors";
import type { DemoHit } from "../lib/demo";
import { slamEase } from "../lib/easing";

type SearchResultListProps = {
  hits: DemoHit[];
  selectedIndex?: number | null;
  visibleCount?: number;
  /** Local scene frame when first result appears */
  resultsFromFrame?: number;
};

export const SearchResultList: React.FC<SearchResultListProps> = ({
  hits,
  selectedIndex = null,
  visibleCount,
  resultsFromFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const shown = hits.slice(0, visibleCount ?? hits.length);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {shown.map((hit, i) => {
        const appearAt = resultsFromFrame + i * 12;
        const pop = interpolate(frame - appearAt, [0, 10], [0.86, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: slamEase,
        });
        const opacity = interpolate(frame - appearAt, [0, 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
        <div
          key={`${hit.filePath}-${hit.startLine}`}
          style={{
            padding: "8px 10px",
            borderRadius: 6,
            background:
              selectedIndex === i
                ? "rgba(9,71,113,0.55)"
                : "rgba(255,255,255,0.03)",
            border:
              selectedIndex === i
                ? "1px solid rgba(0,122,204,0.6)"
                : "1px solid rgba(128,128,128,0.25)",
            opacity,
            scale: pop,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 8,
              marginBottom: 4,
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: "#cccccc",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {hit.filePath}
              <span style={{ color: "#858585", fontWeight: 400 }}>
                :{hit.startLine}
              </span>
            </span>
            <span
              style={{
                fontSize: 10,
                color: "#9cdcfe",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {(hit.score * 100).toFixed(0)}%
            </span>
          </div>
          <div
            style={{
              fontSize: 11,
              color: "#9d9d9d",
              fontFamily: '"SF Mono", Menlo, Monaco, monospace',
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {hit.preview.split("\n")[0]}
          </div>
        </div>
        );
      })}
    </div>
  );
};

type MossSidebarPanelProps = {
  query: string;
  hits: DemoHit[];
  showResults?: boolean;
  selectedIndex?: number | null;
  indexState: "unindexed" | "indexing" | "ready";
  indexProgress?: string;
  createIndexPressed?: boolean;
  visibleHitCount?: number;
  resultsFromFrame?: number;
};

export const MossSidebarPanel: React.FC<MossSidebarPanelProps> = ({
  query,
  hits,
  showResults = false,
  selectedIndex = null,
  indexState,
  indexProgress,
  createIndexPressed = false,
  visibleHitCount,
  resultsFromFrame = 260,
}) => (
  <div
    style={{
      width: 280,
      background: vscode.sidebar,
      display: "flex",
      flexDirection: "column",
      flexShrink: 0,
      borderRight: `1px solid ${vscode.border}`,
      overflow: "hidden",
      fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      padding: 12,
      gap: 10,
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
      }}
    >
      <Img
        src={staticFile("branding/moss/wordmark-light.png")}
        style={{ height: 18, width: "auto", opacity: 0.95 }}
      />
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          border: "1px solid rgba(128,128,128,0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: 0.7,
          fontSize: 14,
          color: "#cccccc",
        }}
      >
        ⚙
      </div>
    </div>

    <div style={{ fontSize: 11, color: "#858585" }}>Semantic code search</div>

    {indexState === "unindexed" && (
      <button
        type="button"
        style={{
          border: "none",
          borderRadius: 6,
          padding: "8px 12px",
          background: createIndexPressed ? "#1177bb" : vscode.buttonBg,
          color: vscode.buttonFg,
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
          scale: createIndexPressed ? 0.97 : 1,
        }}
      >
        Create Index
      </button>
    )}

    {indexState === "indexing" && (
      <div
        style={{
          padding: "8px 10px",
          borderRadius: 6,
          background: "rgba(255,214,10,0.08)",
          border: "1px solid rgba(255,214,10,0.25)",
          fontSize: 12,
          color: "#cccccc",
        }}
      >
        Indexing {indexProgress ?? "…"}
      </div>
    )}

    {indexState === "ready" && (
      <>
        <div
          style={{
            background: vscode.inputBg,
            border: "1px solid #007acc",
            borderRadius: 6,
            padding: "8px 10px",
            fontSize: 12,
            color: "#ffffff",
            minHeight: 36,
            display: "flex",
            alignItems: "flex-start",
            fontFamily: '"SF Mono", Menlo, Monaco, monospace',
            lineHeight: 1.4,
          }}
        >
          <span style={{ wordBreak: "break-word" }}>
            {query}
            <span
              style={{
                display: "inline-block",
                width: 1,
                height: 13,
                background: "#ffffff",
                marginLeft: 1,
                verticalAlign: "text-bottom",
              }}
            />
          </span>
        </div>

        {showResults && (
          <SearchResultList
            hits={hits}
            selectedIndex={selectedIndex}
            visibleCount={visibleHitCount}
            resultsFromFrame={resultsFromFrame}
          />
        )}

        {!showResults && query.length === 0 && (
          <div style={{ fontSize: 11, color: "#858585", marginTop: 4 }}>
            Type a natural-language query…
          </div>
        )}
      </>
    )}
  </div>
);
