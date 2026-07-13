import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadMarkdown } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Upload markdown written by the model directly to the documents directory. Poll grim_status until the path leaves indexing.*.",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Root-relative destination path including filename (e.g. notes/doc.md).",
      },
      markdown: { type: "string", description: "Markdown document body to save and index." },
      description: {
        type: "string",
        description: "Optional short description stored with the indexed document.",
      },
    },
    required: ["path", "markdown"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(
      input,
      "path",
      "Provide a root-relative destination path including filename (e.g. notes/doc.md).",
    );
    if (typeof path !== "string") {
      return path;
    }
    const markdown = requiredString(input, "markdown", "Provide the markdown document body.");
    if (typeof markdown !== "string") {
      return markdown;
    }
    const description = optionalString(input, "description");
    return runTool((config) =>
      uploadMarkdown(config, path, markdown, description, { signal: ctx.signal }),
    );
  },
};
