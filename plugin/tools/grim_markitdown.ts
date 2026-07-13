import path from "node:path";

import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { markitdownUpload } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";
import { openWorkspaceFileBlob } from "../src/workspace.js";

export default {
  description: withSkillReference(
    "Convert a file to markdown without saving or indexing it. Provide workspace_path or content+filename.",
  ),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      workspace_path: { type: "string", description: "Path to a file inside the Vellum workspace." },
      content: { type: "string", description: "Raw bytes as text when workspace_path is omitted." },
      filename: { type: "string", description: "Filename hint when uploading content." },
    },
    required: [],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const workspacePath = optionalString(input, "workspace_path");

    if (workspacePath !== undefined) {
      return runTool(async (config) => {
        const blob = await openWorkspaceFileBlob(ctx.workingDir, workspacePath);
        const filename = path.basename(workspacePath);
        return markitdownUpload(config, { file: blob, filename }, { signal: ctx.signal });
      });
    }

    const content = requiredString(input, "content", "Provide content or workspace_path.");
    if (typeof content !== "string") {
      return content;
    }
    const filename = requiredString(input, "filename", "Provide a filename when converting content.");
    if (typeof filename !== "string") {
      return filename;
    }

    return runTool((config) => {
      const blob = new Blob([content], { type: "application/octet-stream" });
      return markitdownUpload(config, { file: blob, filename }, { signal: ctx.signal });
    });
  },
};
