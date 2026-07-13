import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { getFile } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference("Get indexed content for a file by path."),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Root-relative path of the indexed file." },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(input, "path", "Provide the root-relative path of an indexed file.");
    if (typeof path !== "string") {
      return path;
    }
    return runTool((config) => getFile(config, path, { signal: ctx.signal }));
  },
};
