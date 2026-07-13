import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { uploadDocument } from "../src/client.js";
import {
  optionalBoolean,
  optionalString,
  requiredString,
  runTool,
} from "../src/tool_helpers.js";

export default {
  description:
    "Upload generated or edited text into the knowledge base. Use when you wrote content in-chat and want to index it. Do not use for files already on disk — use krp_upload_workspace instead.",
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      content: {
        type: "string",
        description: "Text content to save and index.",
      },
      filename: {
        type: "string",
        description: "Filename to use on the server (e.g. notes.md).",
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
    required: ["content", "filename"],
  },
  async execute(
    input: Record<string, unknown>,
    ctx: ToolContext,
  ): Promise<ToolExecutionResult> {
    const content = requiredString(input, "content", "Provide non-empty text content to index.");
    if (typeof content !== "string") {
      return content;
    }

    const filename = requiredString(
      input,
      "filename",
      "Provide a filename with a supported extension (e.g. notes.md).",
    );
    if (typeof filename !== "string") {
      return filename;
    }

    return runTool((config) => {
      const blob = new Blob([content], { type: "text/plain; charset=utf-8" });
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
