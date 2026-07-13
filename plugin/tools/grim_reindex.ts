import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { reindex } from "../src/client.js";
import { requiredString, runTool, withSkillReference } from "../src/tool_helpers.js";

export default {
  description: withSkillReference(
    "Force reindex of every indexed document whose path matches a regex. Poll grim_status until matched paths leave indexing.*.",
  ),
  defaultRiskLevel: "medium" as const,
  input_schema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Regex filter on root-relative indexed paths (SurrealDB string::matches).",
      },
    },
    required: ["path"],
  },
  async execute(input: Record<string, unknown>, ctx: ToolContext): Promise<ToolExecutionResult> {
    const path = requiredString(
      input,
      "path",
      "Provide a regex matching root-relative indexed paths (e.g. ^notes/).",
    );
    if (typeof path !== "string") {
      return path;
    }
    return runTool((config) => reindex(config, path, { signal: ctx.signal }));
  },
};
