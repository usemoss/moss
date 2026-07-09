import { CinematicZoomRail, type RailStep } from "./CinematicZoomRail";
import { MOSS_RAIL_TIMING } from "../lib/railTiming";

const VALUE_STEPS: RailStep[] = [
  {
    num: "1",
    title: "Hybrid retrieval",
    subtitle: "Semantic vectors + keyword search in one query.",
    icon: "sparkle",
  },
  {
    num: "2",
    title: "Not a vector database",
    subtitle: "A runtime you call — not infra you run.",
    icon: "check",
  },
  {
    num: "3",
    title: "Local-first",
    subtitle: "Privacy by architecture. Data stays on-device.",
    icon: "folder",
  },
  {
    num: "4",
    title: "Production-ready",
    subtitle: "Sessions, cross-platform indexes, Python & TypeScript SDKs.",
    icon: "bubble",
  },
];

export const MossValueRail: React.FC = () => (
  <CinematicZoomRail
    steps={VALUE_STEPS}
    eyebrow="Why Moss"
    timing={MOSS_RAIL_TIMING}
    verticalOffset={100}
  />
);
