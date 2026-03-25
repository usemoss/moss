import * as fs from "node:fs";

interface TranscriptEntry {
  uuid: string;
  type: string;
  message?: {
    content: string | Array<{ type: string; text?: string }>;
  };
}

interface ParsedMessage {
  role: string;
  content: string;
}

function extractTextContent(message: TranscriptEntry["message"]): string | null {
  if (!message?.content) return null;
  const content = message.content;

  if (typeof content === "string") return content.trim() || null;

  if (Array.isArray(content)) {
    const texts = content
      .filter((block) => block.type === "text" && block.text)
      .map((block) => block.text!.trim())
      .filter(Boolean);
    return texts.length > 0 ? texts.join("\n\n") : null;
  }

  return null;
}

/**
 * Parse a Claude Code JSONL transcript and extract new messages
 * since the last-seen UUID. Returns null if no new messages.
 */
export function extractNewMessages(
  transcriptPath: string,
  lastUuid: string | null
): { messages: ParsedMessage[]; lastUuid: string } | null {
  if (!fs.existsSync(transcriptPath)) return null;

  const raw = fs.readFileSync(transcriptPath, "utf-8");
  const entries: TranscriptEntry[] = raw
    .trim()
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean) as TranscriptEntry[];

  if (entries.length === 0) return null;

  // Find starting point after last-seen UUID
  let startIndex = 0;
  if (lastUuid) {
    const idx = entries.findIndex((e) => e.uuid === lastUuid);
    if (idx >= 0) startIndex = idx + 1;
  }

  const newEntries = entries
    .slice(startIndex)
    .filter((e) => e.type === "user" || e.type === "assistant");

  if (newEntries.length === 0) return null;

  const messages: ParsedMessage[] = newEntries
    .map((entry) => {
      const content = extractTextContent(entry.message);
      if (!content) return null;
      return { role: entry.type, content };
    })
    .filter(Boolean) as ParsedMessage[];

  if (messages.length === 0) return null;

  const newLastUuid = newEntries[newEntries.length - 1].uuid;
  return { messages, lastUuid: newLastUuid };
}
