/** Shared tool execution helpers. */

import type { ToolExecutionResult } from "@vellumai/plugin-api";

import { ApiError } from "./client.js";
import type { PluginConfig } from "./config.js";
import { getState } from "./state.js";
import { WorkspacePathError } from "./workspace.js";

export const KRP_SKILL_PATH = "skills/knowledge-rag-proxy/SKILL.md";

export const KRP_SKILL_REFERENCE = `If unsure which krp_* tool or parameters to use, or calls keep failing, load the knowledge-rag-proxy skill (${KRP_SKILL_PATH}).`;

export function withSkillReference(description: string): string {
  return `${description} ${KRP_SKILL_REFERENCE}`;
}

export interface ToolErrorPayload {
  status: "error";
  message: string;
  hint: string;
}

export interface ReadyState {
  config: PluginConfig;
}

export function requireReadyState(): ReadyState | ToolExecutionResult {
  // Only gate on whether the plugin parsed its config. The server's reachability
  // and auth are not pre-checked here: a stale init-time health flag cannot tell
  // "server down" apart from "token rejected", so we let the real request run and
  // report the precise cause via formatApiError.
  const { config } = getState();
  if (config === null) {
    return errorResult({
      message: "knowledge-rag-proxy plugin not initialized",
      hint: "Set baseUrl and apiToken in the plugin config.json, then restart the assistant.",
    });
  }
  return { config };
}

export function formatApiError(error: unknown): ToolErrorPayload {
  if (error instanceof ApiError) {
    return {
      status: "error",
      message: error.message,
      hint:
        error.hint ??
        fallbackHintForStatus(error.statusCode, error.message),
    };
  }

  if (error instanceof WorkspacePathError) {
    return {
      status: "error",
      message: error.message,
      hint: error.hint,
    };
  }

  // fetch aborts a timed-out or cancelled request with a DOMException.
  if (error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError")) {
    return {
      status: "error",
      message: "Request to the knowledge-rag-proxy server timed out",
      hint: "The server did not respond in time. Check it is running and reachable at baseUrl (host, port, firewall, VPN).",
    };
  }

  // fetch throws a TypeError when the connection itself fails (DNS, refused, TLS).
  if (error instanceof TypeError) {
    return {
      status: "error",
      message: `Cannot reach the knowledge-rag-proxy server: ${error.message}`,
      hint: "The server is unreachable. Verify it is running and that baseUrl in config.json is correct (scheme, host, port).",
    };
  }

  if (error instanceof Error) {
    return {
      status: "error",
      message: error.message,
      hint: "Unexpected client-side error; check the tool arguments and the server logs.",
    };
  }

  return {
    status: "error",
    message: String(error),
    hint: "Unexpected client-side error; check the tool arguments and the server logs.",
  };
}

// The server reached us and answered with an HTTP status but no hint of its own.
// Map each status to its distinct cause so the model fixes the right thing.
function fallbackHintForStatus(statusCode: number, message: string): string {
  if (statusCode === 401) {
    if (message.includes("Missing Bearer token")) {
      return "The plugin sent no Bearer token. Set apiToken in the plugin config.json (same value as KRP_BEARER on the server) and restart the assistant.";
    }
    return "The plugin's apiToken does not match KRP_BEARER on the server. Fix apiToken in the plugin config.json (or KRP_BEARER in the server .env) so they are identical, then restart the assistant.";
  }
  if (statusCode === 403) {
    return "Authenticated but forbidden. Check the server-side access rules for this path.";
  }
  if (statusCode === 404) {
    return "The document was not found on the server. Call krp_list_documents to see indexed filepaths.";
  }
  if (statusCode === 422) {
    return "The request body/params failed validation. Check required fields and their types for this tool.";
  }
  if (statusCode === 503) {
    return "The server is running but not ready: KRP_BEARER is unset or the orchestrator is unavailable. Fix the server .env (KRP_BEARER, KRP_DOCUMENTS_DIR) and restart it. This is a server-side config issue, not a token mismatch.";
  }
  if (statusCode === 400 && message.toLowerCase().includes("reindex")) {
    return "A reindex is already in progress; retry after it finishes.";
  }
  if (statusCode === 400) {
    return "The server rejected the input (e.g. bad path, '..', unsupported format, or destination already exists). Read the message and adjust the arguments.";
  }
  return "Read the message and adjust the arguments, or check the server logs.";
}

export function jsonResult(payload: unknown): ToolExecutionResult {
  return {
    content: JSON.stringify(payload, null, 2),
    isError: false,
  };
}

export function errorResult(payload: Omit<ToolErrorPayload, "status"> & { status?: "error" }): ToolExecutionResult {
  const body: ToolErrorPayload = {
    status: "error",
    message: payload.message,
    hint: payload.hint,
  };
  return {
    content: JSON.stringify(body, null, 2),
    isError: true,
  };
}

export async function runTool<T>(
  action: (config: PluginConfig) => Promise<T>,
): Promise<ToolExecutionResult> {
  const ready = requireReadyState();
  if ("content" in ready) {
    return ready;
  }

  try {
    const result = await action(ready.config);
    return jsonResult(result);
  } catch (error) {
    return errorResult(formatApiError(error));
  }
}

export function optionalString(input: Record<string, unknown>, key: string): string | undefined {
  const value = input[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export function optionalNumber(input: Record<string, unknown>, key: string): number | undefined {
  const value = input[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function optionalBoolean(input: Record<string, unknown>, key: string): boolean | undefined {
  const value = input[key];
  return typeof value === "boolean" ? value : undefined;
}

export function requiredString(
  input: Record<string, unknown>,
  key: string,
  emptyHint: string,
): string | ToolExecutionResult {
  const value = input[key];
  if (typeof value !== "string") {
    return errorResult({
      message: `${key} is required`,
      hint: emptyHint,
    });
  }
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    return errorResult({
      message: `${key} must be non-empty`,
      hint: emptyHint,
    });
  }
  return trimmed;
}
