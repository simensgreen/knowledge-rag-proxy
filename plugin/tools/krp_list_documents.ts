import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { listDocuments } from "../src/client.js";
import { optionalNumber, optionalString, runTool } from "../src/tool_helpers.js";

export default {
  description:
    "List documents in the knowledge base index with optional filters and pagination.",
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      category: {
        type: "string",
        description: "Optional category filter.",
      },
      path: {
        type: "string",
        description: "Optional root-relative directory prefix (e.g. notes or notes/2026).",
      },
      limit: {
        type: "number",
        description: "Maximum documents per page. Default 50.",
      },
      offset: {
        type: "number",
        description: "Pagination offset. Default 0.",
      },
    },
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const limit = optionalNumber(input, "limit") ?? 50;
    const offset = optionalNumber(input, "offset") ?? 0;

    return runTool((config) =>
      listDocuments(
        config,
        {
          category: optionalString(input, "category"),
          path: optionalString(input, "path"),
          limit,
          offset,
        },
        { signal: ctx.signal },
      ),
    );
  },
};
