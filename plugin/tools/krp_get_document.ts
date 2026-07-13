import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { getDocument } from "../src/client.js";
import { requiredString, runTool } from "../src/tool_helpers.js";

export default {
  description:
    "Fetch the full parsed content of an indexed document by its root-relative filepath.",
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      filepath: {
        type: "string",
        description: "Root-relative path to the document (e.g. docs/a.md).",
      },
    },
    required: ["filepath"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const filepath = requiredString(
      input,
      "filepath",
      "Provide a root-relative filepath from krp_list_documents.",
    );
    if (typeof filepath !== "string") {
      return filepath;
    }

    return runTool((config) => getDocument(config, filepath, { signal: ctx.signal }));
  },
};
