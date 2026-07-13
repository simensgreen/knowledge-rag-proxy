/**
 * HTTP client for the self-hosted Grimoire server (`/api/...`).
 */

import type { PluginConfig } from "./config.js";

export interface FetchOptions {
  signal?: AbortSignal;
}

const REQUEST_TIMEOUT_MS = 15000;
const API_PREFIX = "/api";

function buildSignal(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(REQUEST_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}

function authHeaders(config: PluginConfig): Record<string, string> {
  return { Authorization: `Bearer ${config.apiToken}` };
}

function apiUrl(
  config: PluginConfig,
  path: string,
  query?: Record<string, string | number | boolean | undefined>,
): string {
  const params = new URLSearchParams();
  if (query !== undefined) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        params.set(key, String(value));
      }
    }
  }
  const queryString = params.toString();
  return `${config.baseUrl}${API_PREFIX}${path}${queryString.length > 0 ? `?${queryString}` : ""}`;
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

async function parseSuccessEnvelope(response: Response, payload: unknown): Promise<SuccessEnvelope> {
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

async function requestGet(
  config: PluginConfig,
  path: string,
  query: Record<string, string | number | boolean | undefined>,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const response = await fetch(apiUrl(config, path, query), {
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
  });
  const payload = await parseJsonResponse(response);
  return parseSuccessEnvelope(response, payload);
}

async function requestPostQuery(
  config: PluginConfig,
  path: string,
  query: Record<string, string | number | boolean | undefined>,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const response = await fetch(apiUrl(config, path, query), {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
  });
  const payload = await parseJsonResponse(response);
  return parseSuccessEnvelope(response, payload);
}

async function requestPostJson(
  config: PluginConfig,
  path: string,
  query: Record<string, string | number | boolean | undefined>,
  body: Record<string, unknown>,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const response = await fetch(apiUrl(config, path, query), {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: { "Content-Type": "application/json", ...authHeaders(config) },
    body: JSON.stringify(body),
  });
  const payload = await parseJsonResponse(response);
  return parseSuccessEnvelope(response, payload);
}

async function requestMultipart(
  config: PluginConfig,
  path: string,
  formData: FormData,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const response = await fetch(apiUrl(config, path), {
    method: "POST",
    signal: buildSignal(options.signal),
    headers: authHeaders(config),
    body: formData,
  });
  const payload = await parseJsonResponse(response);
  return parseSuccessEnvelope(response, payload);
}

export type ServerReachability =
  | { reachable: true; status: number; authenticated: boolean }
  | { reachable: false; error: string };

export async function probeServerReachable(
  config: PluginConfig,
  options: FetchOptions = {},
): Promise<ServerReachability> {
  try {
    const response = await fetch(apiUrl(config, "/health"), {
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

export async function getFileInfo(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(config, "/file_info", { path }, options);
}

export async function updateFileInfo(
  config: PluginConfig,
  path: string,
  description: string | undefined,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestPostQuery(config, "/file_info", { path, description }, options);
}

export async function getFileContent(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestGet(config, "/file_content", { path }, options);
}

export async function updateFileContent(
  config: PluginConfig,
  path: string,
  markdown: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestPostJson(config, "/file_content", { path }, { markdown }, options);
}

export async function reindex(
  config: PluginConfig,
  path: string,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  return requestPostQuery(config, "/reindex", { path }, options);
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

export interface UploadWorkspaceParams {
  file: Blob;
  filename: string;
  filedir?: string;
  markdown?: string;
  description?: string;
}

export async function uploadWorkspace(
  config: PluginConfig,
  params: UploadWorkspaceParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const formData = new FormData();
  formData.append("file", params.file, params.filename);
  if (params.filedir !== undefined) {
    formData.append("filedir", params.filedir);
  }
  if (params.markdown !== undefined) {
    formData.append("markdown", new Blob([params.markdown], { type: "text/markdown" }), "content.md");
  }
  if (params.description !== undefined) {
    formData.append("description", params.description);
  }
  return requestMultipart(config, "/upload", formData, options);
}

function splitRootRelativePath(path: string): { filedir?: string; filename: string } {
  const trimmed = path.replace(/^\/+/, "").replace(/\/+$/, "");
  const lastSlash = trimmed.lastIndexOf("/");
  if (lastSlash < 0) {
    return { filename: trimmed };
  }
  return {
    filedir: trimmed.slice(0, lastSlash),
    filename: trimmed.slice(lastSlash + 1),
  };
}

export async function uploadMarkdown(
  config: PluginConfig,
  path: string,
  markdown: string,
  description: string | undefined,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const { filedir, filename } = splitRootRelativePath(path);
  if (filename.length === 0) {
    throw new ApiError(400, "path must include a filename", "Use a root-relative path like notes/doc.md.");
  }
  const blob = new Blob([markdown], { type: "text/markdown; charset=utf-8" });
  return uploadWorkspace(
    config,
    { file: blob, filename, filedir, markdown, description },
    options,
  );
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
  const response = await fetch(apiUrl(config, "/download", { path }), {
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
  return requestPostQuery(config, "/remove", { path }, options);
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
  return requestPostQuery(
    config,
    "/move",
    params as unknown as Record<string, string | number | boolean | undefined>,
    options,
  );
}

export interface MarkitdownParams {
  file: Blob;
  filename: string;
}

export async function markitdownUpload(
  config: PluginConfig,
  params: MarkitdownParams,
  options: FetchOptions = {},
): Promise<SuccessEnvelope> {
  const formData = new FormData();
  formData.append("file", params.file, params.filename);
  return requestMultipart(config, "/markitdown", formData, options);
}
