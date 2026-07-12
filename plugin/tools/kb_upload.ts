import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadFile } from "../src/client.js";
import { getState } from "../src/state.js";

export default {
  description:
    "Upload a file from the conversation workspace to the knowledge base for indexing. Use after the user attaches a file they want indexed.",
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      workspace_file_path: {
        type: "string",
        description:
          "Path to the file relative to the workspace or conversation attachments folder.",
      },
      category: {
        type: "string",
        description: "Optional category label for the uploaded document.",
      },
    },
    required: ["workspace_file_path"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const { config, serverHealthy } = getState();
    if (config === null) {
      return { content: "error: knowledge-rag-proxy plugin not initialized", isError: true };
    }
    if (!serverHealthy) {
      return {
        content: "error: knowledge-rag-proxy server unavailable; check baseUrl in config.json",
        isError: true,
      };
    }

    const workspaceFilePath = String(input.workspace_file_path ?? "").trim();
    if (workspaceFilePath.length === 0) {
      return { content: "error: workspace_file_path must be non-empty", isError: true };
    }

    try {
      const result = await uploadFile(config, workspaceFilePath, { signal: ctx.signal });
      return { content: JSON.stringify(result, null, 2), isError: false };
    } catch (error) {
      return { content: `error: ${String(error)}`, isError: true };
    }
  },
};
