import path from "node:path";

import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadDocument } from "../src/client.js";
import {
  optionalBoolean,
  optionalString,
  requiredString,
  runTool,
  withSkillReference,
} from "../src/tool_helpers.js";
import { openWorkspaceFileBlob } from "../src/workspace.js";

export default {
  description: withSkillReference(
    "Upload a file from the Vellum workspace into the knowledge base. Use when the file already exists on disk (chat attachment, scratch, file_read path). Do not paste file bytes — pass workspace_path. Default is save-only; the server watcher indexes later. Set return_document=true to wait for parsing and receive parsed text.",
  ),
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
        description:
          "If true, wait for parsing and include parsed document content in the response. Default false (save-only; watcher indexes later).",
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
      const blob = await openWorkspaceFileBlob(ctx.workingDir, workspacePath);
      const filename = path.basename(workspacePath);
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
