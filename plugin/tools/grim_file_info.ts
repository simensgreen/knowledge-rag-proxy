import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { getFileInfo, updateFileInfo } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Get or update metadata for an indexed file. Omit description to read; pass description to update.",
  ),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Root-relative path of the indexed file." },
      description: {
        type: "string",
        description: "When set, updates the file description instead of reading metadata.",
      },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(input, "path", "Provide the root-relative path of an indexed file.");
    if (typeof path !== "string") {
      return path;
    }
    const description = optionalString(input, "description");
    if (description !== undefined) {
      return runTool((config) => updateFileInfo(config, path, description, { signal: ctx.signal }));
    }
    return runTool((config) => getFileInfo(config, path, { signal: ctx.signal }));
  },
};
