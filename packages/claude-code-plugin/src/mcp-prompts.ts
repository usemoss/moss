import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

interface PromptOptions {
  defaultIndex?: string;
}

export function registerPrompts(server: McpServer, opts: PromptOptions): void {
  const indexHint = opts.defaultIndex
    ? `Default index "${opts.defaultIndex}" is preloaded.`
    : "No default index configured — call load_index first.";

  server.prompt(
    "investigate_bug",
    "Debug a system or error by searching Moss for related runbooks, prior fixes, service docs, and code context.",
    {
      system_or_error: z.string().describe("Error message, system name, or symptom to investigate"),
      indexName: z.string().optional().describe("Index to search (uses default if omitted)"),
    },
    async (args) => {
      const idx = args.indexName || opts.defaultIndex || "<INDEX_NAME>";
      return {
        messages: [
          {
            role: "user" as const,
            content: {
              type: "text" as const,
              text: [
                `Investigate this bug/error: "${args.system_or_error}"`,
                "",
                "Steps:",
                `1. Use the moss \`query\` tool to search index "${idx}" with 2-4 targeted queries:`,
                `   - The exact error message or symptom`,
                `   - The system/service name + "error" or "fix"`,
                `   - Related component names`,
                `   - Prior incident keywords`,
                "2. Synthesize the results into:",
                "   - Likely relevant files/docs",
                "   - Short hypothesis set (what might be wrong)",
                "   - Suggested next steps",
                "",
                indexHint,
              ].join("\n"),
            },
          },
        ],
      };
    }
  );

  server.prompt(
    "understand_system",
    "Search Moss for architecture context, key modules, docs, and entrypoints for a topic.",
    {
      topic: z.string().describe("System, feature, or concept to understand"),
      indexName: z.string().optional().describe("Index to search (uses default if omitted)"),
    },
    async (args) => {
      const idx = args.indexName || opts.defaultIndex || "<INDEX_NAME>";
      return {
        messages: [
          {
            role: "user" as const,
            content: {
              type: "text" as const,
              text: [
                `Help me understand: "${args.topic}"`,
                "",
                "Steps:",
                `1. Use the moss \`query\` tool to search index "${idx}" with broad queries:`,
                `   - "${args.topic}" directly`,
                `   - "${args.topic} architecture" or "${args.topic} design"`,
                `   - Related module/component names`,
                "2. Return a structured map:",
                "   - Key modules and their purpose",
                "   - Relevant docs/ADRs",
                "   - Important terms and concepts",
                "   - Likely entrypoints for exploration",
                "",
                indexHint,
              ].join("\n"),
            },
          },
        ],
      };
    }
  );

  server.prompt(
    "plan_refactor",
    "Search Moss for related patterns, prior migrations, and blast radius before refactoring.",
    {
      area: z.string().describe("Code area, pattern, or system to refactor"),
      indexName: z.string().optional().describe("Index to search (uses default if omitted)"),
    },
    async (args) => {
      const idx = args.indexName || opts.defaultIndex || "<INDEX_NAME>";
      return {
        messages: [
          {
            role: "user" as const,
            content: {
              type: "text" as const,
              text: [
                `Plan a refactor of: "${args.area}"`,
                "",
                "Steps:",
                `1. Use the moss \`query\` tool to search index "${idx}":`,
                `   - "${args.area}" to find current implementation`,
                `   - Similar patterns or abstractions`,
                `   - Prior migrations or refactors in the area`,
                `   - Dependencies and consumers`,
                "2. Return a structured refactor brief:",
                "   - Current state and patterns found",
                "   - Related prior changes",
                "   - Likely blast radius (what else might break)",
                "   - Suggested approach",
                "",
                indexHint,
              ].join("\n"),
            },
          },
        ],
      };
    }
  );

  server.prompt(
    "review_with_context",
    "Search Moss for invariants, similar codepaths, and known caveats before reviewing changes.",
    {
      change_topic: z.string().describe("Topic or area of the change to review"),
      indexName: z.string().optional().describe("Index to search (uses default if omitted)"),
    },
    async (args) => {
      const idx = args.indexName || opts.defaultIndex || "<INDEX_NAME>";
      return {
        messages: [
          {
            role: "user" as const,
            content: {
              type: "text" as const,
              text: [
                `Review context for changes to: "${args.change_topic}"`,
                "",
                "Steps:",
                `1. Use the moss \`query\` tool to search index "${idx}":`,
                `   - Invariants and constraints related to "${args.change_topic}"`,
                `   - Similar codepaths or implementations`,
                `   - Known caveats, gotchas, or edge cases`,
                `   - Architecture decisions (ADRs) related to the area`,
                "2. Return a review prep brief:",
                "   - Key invariants to preserve",
                "   - Similar code to check for consistency",
                "   - Known caveats to watch for",
                "   - Questions to ask the author",
                "",
                indexHint,
              ].join("\n"),
            },
          },
        ],
      };
    }
  );
}
