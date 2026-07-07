import { CinematicZoomRail, type RailStep } from "./CinematicZoomRail";
import { MOSS_RAIL_TIMING } from "../lib/railTiming";

const PLATFORM_STEPS: RailStep[] = [
  {
    num: "1",
    title: "Real-time semantic search",
    subtitle: "A runtime that understands your files.",
    icon: "sparkle",
  },
  {
    num: "2",
    title: "Sub-10ms retrieval",
    subtitle: "Query latency you don't wait on.",
    icon: "check",
  },
  {
    num: "3",
    title: "Runs where you work",
    subtitle: "Embeds in Python & TypeScript — on-device.",
    icon: "bubble",
  },
  {
    num: "4",
    title: "Hybrid retrieval",
    subtitle: "Vectors + keywords. Not a vector database.",
    icon: "folder",
  },
];

export const MossPlatformRail: React.FC = () => (
  <CinematicZoomRail
    steps={PLATFORM_STEPS}
    eyebrow="Moss platform"
    timing={MOSS_RAIL_TIMING}
    verticalOffset={100}
  />
);
