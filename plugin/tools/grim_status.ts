import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { getStatus } from "../src/client.js";
import { runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference("Get index statistics and background indexing status."),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {},
    required: [],
  },
  async execute(_input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    return runTool((config) => getStatus(config, { signal: ctx.signal }));
  },
};
