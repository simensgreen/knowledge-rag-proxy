import path from "node:path";

import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadWorkspace } from "../src/client.js";
import { optionalString, requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";
import { openWorkspaceFileBlob } from "../src/workspace.js";

export default {
  description: withSkillReference(
    "Upload a file from the Vellum workspace to the documents directory (including .md created by the model). Optional markdown supplies ready-to-index text for binaries; optional description is stored with the doc. Poll grim_status until the path leaves indexing.*.",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      workspace_path: {
        type: "string",
        description: "Path to a file inside the Vellum workspace.",
      },
      filedir: {
        type: "string",
        description: "Optional target directory under the documents root on the server.",
      },
      markdown: {
        type: "string",
        description: "Optional ready markdown for indexing when uploading a binary (pdf, image, …).",
      },
      description: {
        type: "string",
        description: "Optional short description stored with the indexed document.",
      },
    },
    required: ["workspace_path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const workspacePath = requiredString(
      input,
      "workspace_path",
      "Provide a path to a file inside the Vellum workspace.",
    );
    if (typeof workspacePath !== "string") {
      return workspacePath;
    }
    const filedir = optionalString(input, "filedir");
    const markdown = optionalString(input, "markdown");
    const description = optionalString(input, "description");

    return runTool(async (config) => {
      const blob = await openWorkspaceFileBlob(ctx.workingDir, workspacePath);
      const filename = path.basename(workspacePath);
      return uploadWorkspace(
        config,
        { file: blob, filename, filedir, markdown, description },
        { signal: ctx.signal },
      );
    });
  },
};
