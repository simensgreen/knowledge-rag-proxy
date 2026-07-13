import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { moveFile } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference("Move a file within the documents directory."),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      source_path: { type: "string", description: "Root-relative source path." },
      dest_path: { type: "string", description: "Root-relative destination path." },
    },
    required: ["source_path", "dest_path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const sourcePath = requiredString(input, "source_path", "Provide the source path including filename.");
    if (typeof sourcePath !== "string") {
      return sourcePath;
    }
    const destPath = requiredString(input, "dest_path", "Provide the destination path including filename.");
    if (typeof destPath !== "string") {
      return destPath;
    }
    return runTool((config) =>
      moveFile(config, { source_path: sourcePath, dest_path: destPath }, { signal: ctx.signal }),
    );
  },
};
