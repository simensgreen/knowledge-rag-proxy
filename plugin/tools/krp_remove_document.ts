import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { removeDocument } from "../src/client.js";
import { optionalBoolean, requiredString, runTool } from "../src/tool_helpers.js";

export default {
  description:
    "Remove a document from the knowledge base. Only when the user explicitly asks to delete. Default removes the file from disk and the index.",
  defaultRiskLevel: "high" as const,
  input_schema: {
    type: "object",
    properties: {
      filepath: {
        type: "string",
        description: "Root-relative path of the document to remove.",
      },
      delete_file: {
        type: "boolean",
        description: "If true, delete the file from disk as well as the index. Default true.",
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

    const deleteFile = optionalBoolean(input, "delete_file") ?? true;

    return runTool((config) =>
      removeDocument(
        config,
        { filepath, deleteFile },
        { signal: ctx.signal },
      ),
    );
  },
};
