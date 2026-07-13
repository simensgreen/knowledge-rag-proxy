import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { removeFile } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference("Remove a file from the documents directory and index."),
  defaultRiskLevel: "high" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Root-relative path of the file to remove." },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(input, "path", "Provide the root-relative path of the file to remove.");
    if (typeof path !== "string") {
      return path;
    }
    return runTool((config) => removeFile(config, path, { signal: ctx.signal }));
  },
};
