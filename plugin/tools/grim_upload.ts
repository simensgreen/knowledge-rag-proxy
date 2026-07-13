import path from "node:path";

import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { upload } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";
import { openWorkspaceFileBlob } from "../src/workspace.js";

export default {
  description: withSkillReference(
    "Upload a file to the documents directory. Provide workspace_path for an on-disk workspace file, or content+filename for generated text.",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      workspace_path: {
        type: "string",
        description: "Path to a file inside the Vellum workspace.",
      },
      content: {
        type: "string",
        description: "Text content to save when workspace_path is omitted.",
      },
      filename: {
        type: "string",
        description: "Filename when uploading content (required with content).",
      },
      filedir: {
        type: "string",
        description: "Optional target directory under the documents root on the server.",
      },
    },
    required: [],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const workspacePath = optionalString(input, "workspace_path");
    const content = optionalString(input, "content");
    const filedir = optionalString(input, "filedir");

    if (workspacePath !== undefined) {
      return runTool(async (config) => {
        const blob = await openWorkspaceFileBlob(ctx.workingDir, workspacePath);
        const filename = path.basename(workspacePath);
        return upload(config, { file: blob, filename, filedir }, { signal: ctx.signal });
      });
    }

    const text = requiredString(input, "content", "Provide content or workspace_path.");
    if (typeof text !== "string") {
      return text;
    }
    const filename = requiredString(
      input,
      "filename",
      "Provide a filename when uploading content (e.g. notes.md).",
    );
    if (typeof filename !== "string") {
      return filename;
    }

    return runTool((config) => {
      const blob = new Blob([text], { type: "text/plain; charset=utf-8" });
      return upload(config, { file: blob, filename, filedir }, { signal: ctx.signal });
    });
  },
};
