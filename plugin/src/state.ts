import type { PluginConfig } from "./config.js";

export interface PluginRuntimeState {
  config: PluginConfig | null;
  workspaceDir: string | null;
  processedAttachments: Set<string>;
}

let runtimeState: PluginRuntimeState = {
  config: null,
  workspaceDir: null,
  processedAttachments: new Set(),
};

export function getState(): PluginRuntimeState {
  return runtimeState;
}

export function setState(partial: Partial<PluginRuntimeState>): void {
  runtimeState = { ...runtimeState, ...partial };
}

export function requireConfig(): PluginConfig {
  const config = runtimeState.config;
  if (config === null) {
    throw new Error("knowledge-rag-proxy: plugin not initialized");
  }
  return config;
}

export function attachmentProcessKey(conversationId: string, attachmentId: string): string {
  return `${conversationId}:${attachmentId}`;
}

export function markAttachmentProcessed(conversationId: string, attachmentId: string): void {
  runtimeState.processedAttachments.add(attachmentProcessKey(conversationId, attachmentId));
}

export function isAttachmentProcessed(conversationId: string, attachmentId: string): boolean {
  return runtimeState.processedAttachments.has(attachmentProcessKey(conversationId, attachmentId));
}
