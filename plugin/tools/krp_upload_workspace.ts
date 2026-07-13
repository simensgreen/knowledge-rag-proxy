import path from "node:path";

import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadDocument } from "../src/client.js";
import {
  optionalBoolean,
  optionalString,
  requiredString,
  runTool,
} from "../src/tool_helpers.js";
import { readWorkspaceFile } from "../src/workspace.js";

export default {
  description:
    "Upload a file from the Vellum workspace into the knowledge base. Use when the file already exists on disk (chat attachment, scratch, file_read path). Do not paste file bytes — pass workspace_path.",
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      workspace_path: {
        type: "string",
        description: "Path to the file inside the Vellum workspace.",
      },
      filedir: {
        type: "string",
        description: "Optional target directory under the documents root on the server.",
      },
      category: {
        type: "string",
        description: "Optional category for indexing.",
      },
      return_document: {
        type: "boolean",
        description: "If true, include parsed document content in the response. Default false.",
      },
    },
    required: ["workspace_path"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const workspacePath = requiredString(
      input,
      "workspace_path",
      "Provide the workspace-relative path to an existing file.",
    );
    if (typeof workspacePath !== "string") {
      return workspacePath;
    }

    return runTool(async (config) => {
      const bytes = await readWorkspaceFile(ctx.workingDir, workspacePath);
      const filename = path.basename(workspacePath);
      const blob = new Blob([Uint8Array.from(bytes)]);
      return uploadDocument(
        config,
        {
          file: blob,
          filename,
          filedir: optionalString(input, "filedir"),
          category: optionalString(input, "category"),
          returnDocument: optionalBoolean(input, "return_document") ?? false,
        },
        { signal: ctx.signal },
      );
    });
  },
};
