import { createFoundingAgentSession } from "@moss-tools/founding-agent";

export async function POST() {
  const apiKey = process.env.MOSS_FA_API_KEY;
  if (!apiKey) {
    return Response.json({ error: "MOSS_FA_API_KEY is not set" }, { status: 500 });
  }
  try {
    const session = await createFoundingAgentSession({ apiKey });
    return Response.json(session);
  } catch (error) {
    console.error("Failed to create founding agent session:", error);
    return Response.json(
      { error: error instanceof Error ? error.message : "Session creation failed" },
      { status: 500 },
    );
  }
}
