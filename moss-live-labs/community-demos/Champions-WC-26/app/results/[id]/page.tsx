import { ResultsLoader } from "../../../components/game/results-loader";

export default async function ResultsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResultsLoader id={id} />;
}
