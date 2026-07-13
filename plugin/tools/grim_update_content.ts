import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { getFileContent, updateFileContent } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Read or replace reconstructed markdown for an indexed file. Omit markdown to read; pass markdown to queue a reindex (poll grim_status until the path leaves indexing.*).",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Root-relative path of the indexed file." },
      markdown: {
        type: "string",
        description: "When set, replaces indexed markdown content (does not change the on-disk binary).",
      },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(input, "path", "Provide the root-relative path of an indexed file.");
    if (typeof path !== "string") {
      return path;
    }
    const markdown = optionalString(input, "markdown");
    if (markdown !== undefined) {
      return runTool((config) => updateFileContent(config, path, markdown, { signal: ctx.signal }));
    }
    return runTool((config) => getFileContent(config, path, { signal: ctx.signal }));
  },
};
