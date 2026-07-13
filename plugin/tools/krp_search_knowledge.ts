import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { searchKnowledge } from "../src/client.js";
import {
  optionalBoolean,
  optionalNumber,
  optionalString,
  requiredString,
  runTool,
} from "../src/tool_helpers.js";

export default {
  description:
    "Search indexed documents in the knowledge base. Use when the user asks to find information in their documents.",
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "Search query text.",
      },
      max_results: {
        type: "number",
        description: "Maximum number of hits to return. Default 5.",
      },
      category: {
        type: "string",
        description: "Optional category filter.",
      },
      hybrid_alpha: {
        type: "number",
        description: "Hybrid search alpha between 0 (keyword) and 1 (semantic). Default 0.3.",
      },
      min_score: {
        type: "number",
        description: "Minimum relevance score. Default 0.",
      },
      snippet_mode: {
        type: "boolean",
        description: "Return truncated snippets instead of full chunks. Default true.",
      },
    },
    required: ["query"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const query = requiredString(
      input,
      "query",
      "Provide a non-empty query with 1-3 keywords or a short phrase.",
    );
    if (typeof query !== "string") {
      return query;
    }

    return runTool((config) =>
      searchKnowledge(
        config,
        {
          query,
          max_results: optionalNumber(input, "max_results"),
          category: optionalString(input, "category"),
          hybrid_alpha: optionalNumber(input, "hybrid_alpha"),
          min_score: optionalNumber(input, "min_score"),
          snippet_mode: optionalBoolean(input, "snippet_mode"),
        },
        { signal: ctx.signal },
      ),
    );
  },
};
