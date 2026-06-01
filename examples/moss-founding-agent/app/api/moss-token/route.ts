import { createFoundingAgentSession } from "@moss-tools/founding-agent";

export async function POST() {
  const session = await createFoundingAgentSession({
    apiKey: process.env.MOSS_FA_API_KEY!,
  });
  return Response.json(session);
}
