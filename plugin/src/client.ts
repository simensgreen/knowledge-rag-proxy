/**
 * HTTP client for the self-hosted knowledge-rag-proxy server.
 *
 * Bearer tokens are NOT set here. Configure the matching credential in the
 * Vellum vault with allowedDomains = host(baseUrl); CES injects Authorization
 * at the network layer.
 *
 * TODO Phase 2: implement request helpers and error formatting.
 */

import type { PluginConfig } from "./config.js";

export interface FetchOptions {
  signal?: AbortSignal;
}

async function requestJson(
  config: PluginConfig,
  path: string,
  init: RequestInit & FetchOptions,
): Promise<unknown> {
  const url = `${config.baseUrl}${path}`;
  const response = await fetch(url, {
    ...init,
    signal: init.signal,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`knowledge-rag-proxy: ${response.status} ${response.statusText}: ${body}`);
  }
  return response.json();
}

export async function checkHealth(config: PluginConfig, options: FetchOptions = {}): Promise<boolean> {
  const url = `${config.baseUrl}/health`;
  const response = await fetch(url, { signal: options.signal });
  if (!response.ok) {
    return false;
  }
  const payload = (await response.json()) as { ok?: boolean };
  return payload.ok === true;
}

export async function search(
  config: PluginConfig,
  body: { query: string; max_results?: number; category?: string | null },
  options: FetchOptions = {},
): Promise<unknown> {
  return requestJson(config, "/search", {
    method: "POST",
    body: JSON.stringify(body),
    signal: options.signal,
  });
}

export async function listDocuments(
  config: PluginConfig,
  query: { category?: string; limit?: number },
  options: FetchOptions = {},
): Promise<unknown> {
  const params = new URLSearchParams();
  if (query.category !== undefined) {
    params.set("category", query.category);
  }
  if (query.limit !== undefined) {
    params.set("limit", String(query.limit));
  }
  const queryString = params.toString();
  const path = queryString.length > 0 ? `/list?${queryString}` : "/list";
  const url = `${config.baseUrl}${path}`;
  const response = await fetch(url, { signal: options.signal });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`knowledge-rag-proxy: ${response.status}: ${text}`);
  }
  return response.json();
}

export async function uploadFile(
  _config: PluginConfig,
  _workspaceFilePath: string,
  _options: FetchOptions = {},
): Promise<unknown> {
  // TODO Phase 2: read file from workspace path, POST multipart to /upload
  throw new Error("knowledge-rag-proxy: kb_upload not implemented yet");
}
