import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { listFiles } from "../src/client.js";
import { optionalNumber, optionalString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference("List indexed files, optionally filtered by a path regex."),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Optional regex filter on root-relative paths." },
      limit: { type: "number", description: "Page size (default 50)." },
      offset: { type: "number", description: "Page offset (default 0)." },
    },
    required: [],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    return runTool((config) =>
      listFiles(
        config,
        {
          path: optionalString(input, "path"),
          limit: optionalNumber(input, "limit"),
          offset: optionalNumber(input, "offset"),
        },
        { signal: ctx.signal },
      ),
    );
  },
};
