/** Parsed plugin config from config.json. */

export interface PluginConfig {
  baseUrl: string;
  apiToken: string;
  autoIndexAttachments: boolean;
  injectAttachmentDocument: boolean;
  attachmentFiledir: string;
  attachmentMaxInjectChars: number;
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

  const attachmentFiledir =
    typeof record.attachmentFiledir === "string" && record.attachmentFiledir.trim().length > 0
      ? record.attachmentFiledir.trim().replace(/^\/+|\/+$/g, "")
      : "vellum";

  const attachmentMaxInjectChars =
    typeof record.attachmentMaxInjectChars === "number" &&
    Number.isFinite(record.attachmentMaxInjectChars) &&
    record.attachmentMaxInjectChars > 0
      ? Math.floor(record.attachmentMaxInjectChars)
      : 20_000;

  return {
    baseUrl,
    apiToken,
    autoIndexAttachments: record.autoIndexAttachments !== false,
    injectAttachmentDocument: record.injectAttachmentDocument !== false,
    attachmentFiledir,
    attachmentMaxInjectChars,
  };
}
