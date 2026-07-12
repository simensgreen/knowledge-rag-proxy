import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { listDocuments } from "../src/client.js";
import { getState } from "../src/state.js";

export default {
  description:
    "List documents in the knowledge base index. Use when the user wants an overview of indexed files.",
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      category: {
        type: "string",
        description: "Optional category filter.",
      },
      limit: {
        type: "number",
        description: "Maximum documents to return. Default 50.",
      },
    },
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

    const category = typeof input.category === "string" ? input.category : undefined;
    const limit = typeof input.limit === "number" ? input.limit : undefined;

    try {
      const result = await listDocuments(config, { category, limit }, { signal: ctx.signal });
      return { content: JSON.stringify(result, null, 2), isError: false };
    } catch (error) {
      return { content: `error: ${String(error)}`, isError: true };
    }
  },
};
