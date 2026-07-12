import type { PluginConfig } from "./config.js";

export interface PluginRuntimeState {
  config: PluginConfig | null;
  serverHealthy: boolean;
}

let runtimeState: PluginRuntimeState = {
  config: null,
  serverHealthy: false,
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
