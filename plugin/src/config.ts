/** Parsed plugin config from config.json. */

export interface PluginConfig {
  baseUrl: string;
  apiToken: string;
}

export function parsePluginConfig(raw: unknown): PluginConfig {
  if (raw === null || typeof raw !== "object") {
    throw new Error("knowledge-rag-proxy: config must be an object");
  }
  const record = raw as Record<string, unknown>;

  const baseUrl = String(record.baseUrl ?? "").trim().replace(/\/$/, "");
  if (baseUrl.length === 0) {
    throw new Error("knowledge-rag-proxy: config.baseUrl is required");
  }
  if (!baseUrl.startsWith("http://") && !baseUrl.startsWith("https://")) {
    throw new Error("knowledge-rag-proxy: config.baseUrl must be http:// or https://");
  }

  const apiToken = String(record.apiToken ?? "").trim();
  if (apiToken.length === 0) {
    throw new Error("knowledge-rag-proxy: config.apiToken is required (same value as KRP_BEARER on the server)");
  }

  return {
    baseUrl,
    apiToken,
  };
}
