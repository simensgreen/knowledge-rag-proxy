import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { download } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";
import { writeScratchFile } from "../src/workspace.js";

const DOWNLOAD_SCRATCH_DIR = "scratch/grimoire/downloads";

export default {
  description: withSkillReference(
    "Download a file from the documents directory to workspace scratch (metadata only in the tool result).",
  ),
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      path: { type: "string", description: "Root-relative path of the file to download." },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const filePath = requiredString(input, "path", "Provide the root-relative path of the file to download.");
    if (typeof filePath !== "string") {
      return filePath;
    }

    return runTool(async (config) => {
      const result = await download(config, filePath, { signal: ctx.signal });
      const scratchPath = await writeScratchFile(
        ctx.workingDir,
        `${DOWNLOAD_SCRATCH_DIR}/${result.filename}`,
        result.bytes,
      );
      return {
        path: filePath,
        scratch_path: scratchPath,
        filename: result.filename,
        media_type: result.mediaType,
        byte_length: result.bytes.byteLength,
      };
    });
  },
};
