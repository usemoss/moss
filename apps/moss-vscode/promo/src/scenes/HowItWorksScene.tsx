import { AbsoluteFill, useCurrentFrame } from "remotion";
import {
  ChunkVisual,
  EmbedVisual,
  PipelineBeat,
  QueryVisual,
  ScanVisual,
} from "../components/PipelineBeat";
import { SceneBridge } from "../components/SceneBridge";
import { SequoiaBackdrop } from "../components/SequoiaBackdrop";
import { SCENES } from "../lib/timing";

const BEATS = [
  { start: 0, end: 70, title: "Scan your workspace", subtitle: "Every file. Locally." },
  { start: 70, end: 140, title: "Chunk by meaning", subtitle: "Code becomes searchable units." },
  { start: 140, end: 210, title: "Embed on-device", subtitle: "No embedding API. No network hop." },
  { start: 210, end: 283, title: "Query in milliseconds", subtitle: "Semantic search at editor speed." },
] as const;

export const HowItWorksScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <SequoiaBackdrop scrimOpacity={0.48}>
      <SceneBridge sceneDuration={SCENES.howItWorks.duration} exitDuration={12}>
        <AbsoluteFill>
          <div
            style={{
              position: "absolute",
              top: 64,
              left: 0,
              right: 0,
              textAlign: "center",
              fontSize: 18,
              fontWeight: 600,
              letterSpacing: 4,
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.45)",
              fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
            }}
          >
            How it works
          </div>

          <PipelineBeat
            title={BEATS[0].title}
            subtitle={BEATS[0].subtitle}
            startFrame={BEATS[0].start}
            endFrame={BEATS[0].end}
          >
            <ScanVisual localFrame={frame - BEATS[0].start} />
          </PipelineBeat>
          <PipelineBeat
            title={BEATS[1].title}
            subtitle={BEATS[1].subtitle}
            startFrame={BEATS[1].start}
            endFrame={BEATS[1].end}
          >
            <ChunkVisual localFrame={frame - BEATS[1].start} />
          </PipelineBeat>
          <PipelineBeat
            title={BEATS[2].title}
            subtitle={BEATS[2].subtitle}
            startFrame={BEATS[2].start}
            endFrame={BEATS[2].end}
          >
            <EmbedVisual localFrame={frame - BEATS[2].start} />
          </PipelineBeat>
          <PipelineBeat
            title={BEATS[3].title}
            subtitle={BEATS[3].subtitle}
            startFrame={BEATS[3].start}
            endFrame={BEATS[3].end}
          >
            <QueryVisual localFrame={frame - BEATS[3].start} />
          </PipelineBeat>
        </AbsoluteFill>
      </SceneBridge>
    </SequoiaBackdrop>
  );
};
