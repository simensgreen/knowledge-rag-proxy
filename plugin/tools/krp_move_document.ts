import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { moveDocument } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Move or rename an indexed file within the documents root. Both paths must be full root-relative paths including the filename. Fails if the destination already exists.",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      source_filepath: {
        type: "string",
        description: "Current root-relative path including filename (e.g. notes/a.md).",
      },
      dest_filepath: {
        type: "string",
        description: "New root-relative path including filename (e.g. archive/2026/a.md).",
      },
    },
    required: ["source_filepath", "dest_filepath"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const source_filepath = requiredString(
      input,
      "source_filepath",
      "Provide the current root-relative path including the filename.",
    );
    if (typeof source_filepath !== "string") {
      return source_filepath;
    }

    const dest_filepath = requiredString(
      input,
      "dest_filepath",
      "Provide the destination root-relative path including the filename.",
    );
    if (typeof dest_filepath !== "string") {
      return dest_filepath;
    }

    return runTool((config) =>
      moveDocument(
        config,
        { source_filepath, dest_filepath },
        { signal: ctx.signal },
      ),
    );
  },
};
