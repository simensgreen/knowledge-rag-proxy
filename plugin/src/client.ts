/**
 * HTTP client for the self-hosted Grimoire server.
 */

import type { PluginConfig } from "./config.js";

export interface FetchOptions {
  signal?: AbortSignal;
}

const REQUEST_TIMEOUT_MS = 15000;

function buildSignal(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

function authHeaders(config: PluginConfig): Record<string, string> {
  return { Authorization: `Bearer ${config.apiToken}` };
}

export interface ApiErrorBody {
  status: "error";
  message: string;
  hint?: string;
}

export class ApiError extends Error {
  readonly statusCode: number;
  readonly hint: string | undefined;

  constructor(statusCode: number, message: string, hint?: string) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.hint = hint;
  }
}

interface SuccessEnvelope {
  status: "success";
  [key: string]: unknown;
}

function parseErrorBody(raw: unknown): { message: string; hint?: string } {
  if (raw !== null && typeof raw === "object") {
    const record = raw as Record<string, unknown>;
    const message = typeof record.message === "string" ? record.message : "Request failed";
    const hint = typeof record.hint === "string" ? record.hint : undefined;
    return { message, hint };
  }
  return { message: "Request failed" };
}

async function parseJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { status: "error", message: text };
  }
}

async function requestGet(
  config: PluginConfig,
  path: string,
  query: Record<string, string | number | boolean | undefined>,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  }
  const queryString = params.toString();
  const url = `${config.baseUrl}${path}${queryString.length > 0 ? `?${queryString}` : ""}`;
  const response = await fetch(url, {
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
  });
  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    const { message, hint } = parseErrorBody(payload);
    throw new ApiError(response.status, message, hint);
  }

  if (payload === null || typeof payload !== "object") {
    throw new ApiError(response.status, "Invalid response from server");
  }

  const envelope = payload as Record<string, unknown>;
  if (envelope.status === "error") {
    const { message, hint } = parseErrorBody(envelope);
    throw new ApiError(response.status, message, hint);
  }

  return envelope as SuccessEnvelope;
}

async function requestJson(
  config: PluginConfig,
  path: string,
  body: Record<string, unknown>,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const url = `${config.baseUrl}${path}`;
  const response = await fetch(url, {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: { "Content-Type": "application/json", ...authHeaders(config) },
    body: JSON.stringify(body),
  });
  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    const { message, hint } = parseErrorBody(payload);
    throw new ApiError(response.status, message, hint);
  }

  if (payload === null || typeof payload !== "object") {
    throw new ApiError(response.status, "Invalid response from server");
  }

  const envelope = payload as Record<string, unknown>;
  if (envelope.status === "error") {
    const { message, hint } = parseErrorBody(envelope);
    throw new ApiError(response.status, message, hint);
  }

  return envelope as SuccessEnvelope;
}

export type ServerReachability =
  | { reachable: true; status: number; authenticated: boolean }
  | { reachable: false; error: string };

export async function probeServerReachable(
  config: PluginConfig,
  options: FetchOptions = {},
): Promise<ServerReachability> {
  try {
    const response = await fetch(`${config.baseUrl}/health`, {
      signal: buildSignal(options.signal),
      headers: authHeaders(config),
    });
    return { reachable: true, status: response.status, authenticated: response.ok };
  } catch (error) {
    return { reachable: false, error: error instanceof Error ? error.message : String(error) };
  }
}

export interface SearchParams {
  query: string;
  max_results?: number;
}

export async function search(
  config: PluginConfig,
  params: SearchParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(
    config,
    "/search",
    params as unknown as Record<string, string | number | boolean | undefined>,
    options,
  );
}

export async function getFile(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(config, "/file", { path }, options);
}

export interface ListFilesParams {
  path?: string;
  limit?: number;
  offset?: number;
}

export async function listFiles(
  config: PluginConfig,
  params: ListFilesParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(
    config,
    "/list_files",
    params as unknown as Record<string, string | number | boolean | undefined>,
    options,
  );
}

export async function getStatus(
  config: PluginConfig,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(config, "/status", {}, options);
}

export interface UploadParams {
  file: Blob;
  filename: string;
  filedir?: string;
}

export async function upload(
  config: PluginConfig,
  params: UploadParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const formData = new FormData();
  formData.append("file", params.file, params.filename);
  if (params.filedir !== undefined) {
    formData.append("filedir", params.filedir);
  }

  const url = `${config.baseUrl}/upload`;
  const response = await fetch(url, {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
    body: formData,
  });
  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    const { message, hint } = parseErrorBody(payload);
    throw new ApiError(response.status, message, hint);
  }

  if (payload === null || typeof payload !== "object") {
    throw new ApiError(response.status, "Invalid response from server");
  }

  const envelope = payload as Record<string, unknown>;
  if (envelope.status === "error") {
    const { message, hint } = parseErrorBody(envelope);
    throw new ApiError(response.status, message, hint);
  }

  return envelope as SuccessEnvelope;
}

export interface DownloadResult {
  bytes: Uint8Array;
  mediaType: string;
  filename: string;
}

function parseContentDispositionFilename(header: string | null): string | undefined {
  if (header === null) {
    return undefined;
  }
  const filenameMatch = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header);
  if (filenameMatch === null) {
    return undefined;
  }
  const captured = filenameMatch[1];
  if (captured === undefined) {
    return undefined;
  }
  return decodeURIComponent(captured.replace(/"/g, ""));
}

export async function download(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<DownloadResult> {
  const params = new URLSearchParams({ path });
  const url = `${config.baseUrl}/download?${params.toString()}`;
  const response = await fetch(url, {
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
  });

  if (!response.ok) {
    const payload = await parseJsonResponse(response);
    const { message, hint } = parseErrorBody(payload);
    throw new ApiError(response.status, message, hint);
  }

  const bytes = new Uint8Array(await response.arrayBuffer());
  const mediaType = response.headers.get("content-type") ?? "application/octet-stream";
  const filename =
    parseContentDispositionFilename(response.headers.get("content-disposition")) ??
    path.split("/").pop() ??
    "download.bin";

  return { bytes, mediaType, filename };
}

export async function removeFile(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestJson(config, "/remove", { path }, options);
}

export interface MoveParams {
  source_path: string;
  dest_path: string;
}

export async function moveFile(
  config: PluginConfig,
  params: MoveParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestJson(config, "/move", params as unknown as Record<string, unknown>, options);
}

export async function markitdownUpload(
  config: PluginConfig,
  params: UploadParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const formData = new FormData();
  formData.append("file", params.file, params.filename);

  const url = `${config.baseUrl}/markitdown`;
  const response = await fetch(url, {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
    body: formData,
  });
  const payload = await parseJsonResponse(response);

  if (!response.ok) {
    const { message, hint } = parseErrorBody(payload);
    throw new ApiError(response.status, message, hint);
  }

  if (payload === null || typeof payload !== "object") {
    throw new ApiError(response.status, "Invalid response from server");
  }

  const envelope = payload as Record<string, unknown>;
  if (envelope.status === "error") {
    const { message, hint } = parseErrorBody(envelope);
    throw new ApiError(response.status, message, hint);
  }

  return envelope as SuccessEnvelope;
}
