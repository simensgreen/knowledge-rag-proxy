/** Parsed plugin config from config.json (non-secret fields only). */

export interface PluginConfig {
  baseUrl: string;
  apiTokenCredentialRef: string;
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

  const apiTokenCredentialRef = String(record.apiTokenCredentialRef ?? "").trim();
  if (apiTokenCredentialRef.length === 0) {
    throw new Error("knowledge-rag-proxy: config.apiTokenCredentialRef is required");
  }

  return { baseUrl, apiTokenCredentialRef };
}
