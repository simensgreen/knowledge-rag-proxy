import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { downloadDocument } from "../src/client.js";
import { jsonResult, requireReadyState, formatApiError, errorResult, requiredString, withSkillReference } from "../src/tool_helpers.js";
import { writeScratchFile } from "../src/workspace.js";

export default {
  description: withSkillReference(
    "Download a document from the knowledge base into the Vellum workspace scratch area. Returns metadata and workspace_path only — use file_read to read the file.",
  ),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      filepath: {
        type: "string",
        description: "Root-relative path on the server (e.g. docs/a.md).",
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

    const ready = requireReadyState();
    if ("content" in ready) {
      return ready;
    }

    try {
      const downloaded = await downloadDocument(ready.config, filepath, { signal: ctx.signal });
      const scratchRelative = `downloads/${filepath}`;
      const workspacePath = await writeScratchFile(ctx.workingDir, scratchRelative, downloaded.bytes);

      return jsonResult({
        status: "success",
        filepath,
        workspace_path: workspacePath,
        size_bytes: downloaded.bytes.byteLength,
        media_type: downloaded.mediaType,
      });
    } catch (error) {
      return errorResult(formatApiError(error));
    }
  },
};
