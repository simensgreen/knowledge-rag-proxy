import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { search } from "../src/client.js";
import { optionalNumber, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Search indexed documents in the knowledge base.",
  ),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Search query text." },
      max_results: { type: "number", description: "Maximum number of hits to return." },
    },
    required: ["query"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const query = requiredString(input, "query", "Provide a non-empty search query.");
    if (typeof query !== "string") {
      return query;
    }
    return runTool((config) =>
      search(config, { query, max_results: optionalNumber(input, "max_results") }, { signal: ctx.signal }),
    );
  },
};
