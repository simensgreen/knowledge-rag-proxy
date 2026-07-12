import type { ToolContext, ToolExecutionResult } from "@vellumai/plugin-api";

import { search } from "../src/client.js";
import { getState } from "../src/state.js";

export default {
  description:
    "Search the knowledge base for documents matching a query. Use when the user asks to find information in their indexed documents.",
  defaultRiskLevel: "low" as const,
  input_schema: {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "Search query text.",
      },
      max_results: {
        type: "number",
        description: "Maximum number of hits to return. Default 5.",
      },
      category: {
        type: "string",
        description: "Optional category filter.",
      },
    },
    required: ["query"],
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

    const query = String(input.query ?? "").trim();
    if (query.length === 0) {
      return { content: "error: query must be non-empty", isError: true };
    }

    const maxResults = input.max_results;
    const category = input.category;

    try {
      const result = await search(
        config,
        {
          query,
          max_results: typeof maxResults === "number" ? maxResults : undefined,
          category: typeof category === "string" ? category : null,
        },
        { signal: ctx.signal },
      );
      return { content: JSON.stringify(result, null, 2), isError: false };
    } catch (error) {
      return { content: `error: ${String(error)}`, isError: true };
    }
  },
};
